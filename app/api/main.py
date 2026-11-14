"""shopfront api: products (Postgres), carts (Redis), order intake (Redis queue), receipts (shared volume)."""

import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg_pool import ConnectionPool, PoolTimeout

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s api %(message)s",
)
log = logging.getLogger("api")

DSN = (
    f"host={os.environ['DB_HOST']} port={os.getenv('DB_PORT', '5432')} "
    f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASSWORD']} connect_timeout=2"
)
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "3"))
RECEIPTS_DIR = os.getenv("RECEIPTS_DIR", "/data/receipts")

pool = ConnectionPool(DSN, min_size=1, max_size=POOL_MAX, timeout=POOL_TIMEOUT, open=False)
rds = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

app = FastAPI()

# --- tiny in-process metrics -------------------------------------------------
_lat = defaultdict(lambda: deque(maxlen=500))
_count = defaultdict(int)
_errors = defaultdict(int)


@app.on_event("startup")
def _startup() -> None:
    try:
        pool.open(wait=False)
    except Exception as exc:  # keep serving /health so the failure is visible in logs, not a crash loop
        log.error("db pool open failed: %s", exc)
    log.info("api started pool_max=%s db_host=%s", POOL_MAX, os.environ["DB_HOST"])


@app.middleware("http")
async def _metrics(request: Request, call_next):
    route = request.url.path.split("/")[1] or "root"
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        _errors[route] += 1
        raise
    ms = (time.perf_counter() - start) * 1000
    _lat[route].append(ms)
    _count[route] += 1
    if response.status_code >= 500:
        _errors[route] += 1
    log.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(PoolTimeout)
async def _pool_timeout(_: Request, exc: PoolTimeout):
    log.error("PoolTimeout: couldn't get a connection after %.1f sec (pool max_size=%s)", POOL_TIMEOUT, POOL_MAX)
    return JSONResponse({"error": "database busy"}, status_code=503)


@app.exception_handler(redis.exceptions.ResponseError)
async def _redis_error(_: Request, exc: redis.exceptions.ResponseError):
    log.error("redis error: %s", exc)
    return JSONResponse({"error": "cache error"}, status_code=500)


@app.exception_handler(Exception)
async def _any_error(_: Request, exc: Exception):
    log.exception("unhandled error: %s", exc)
    return JSONResponse({"error": "internal error"}, status_code=500)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    out = {}
    for route, samples in _lat.items():
        s = sorted(samples)
        out[route] = {
            "count": _count[route],
            "errors": _errors[route],
            "p50_ms": round(s[len(s) // 2], 1) if s else None,
            "p95_ms": round(s[int(len(s) * 0.95) - 1], 1) if s else None,
        }
    try:
        out["queue"] = {
            "orders_pending": rds.llen("orders"),
            "orders_processing": rds.llen("orders:processing"),
            "orders_failed": rds.llen("orders:failed"),
        }
    except Exception as exc:
        out["queue"] = {"error": str(exc)}
    return out


# --- products ---------------------------------------------------------------
@app.get("/products")
def products(category: str = "cat-1"):
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, name, price FROM products WHERE category = %s ORDER BY price LIMIT 20",
            (category,),
        ).fetchall()
    return [{"id": r[0], "name": r[1], "price": float(r[2])} for r in rows]


@app.get("/products/{pid}")
def product(pid: int):
    with pool.connection() as conn:
        # Simulates a slightly heavier lookup (reviews, stock) that holds the connection briefly.
        conn.execute("SELECT pg_sleep(0.05)")
        row = conn.execute("SELECT id, name, price, category FROM products WHERE id = %s", (pid,)).fetchone()
    if not row:
        raise HTTPException(404)
    return {"id": row[0], "name": row[1], "price": float(row[2]), "category": row[3]}


# --- carts ------------------------------------------------------------------
@app.post("/cart/{user}")
async def add_to_cart(user: str, request: Request):
    body = await request.json()
    rds.hset(f"cart:{user}", str(body["product_id"]), json.dumps(body))
    rds.expire(f"cart:{user}", 3600)
    return {"ok": True}


@app.get("/cart/{user}")
def get_cart(user: str):
    return {k: json.loads(v) for k, v in rds.hgetall(f"cart:{user}").items()}


# --- orders -----------------------------------------------------------------
@app.post("/orders", status_code=202)
async def create_order(request: Request):
    body = await request.json()
    order = {"id": str(uuid.uuid4()), "user_id": body["user_id"], "items": body["items"]}
    rds.lpush("orders", json.dumps(order))
    return {"id": order["id"], "status": "queued"}


@app.get("/orders/{oid}/receipt", response_class=PlainTextResponse)
def receipt(oid: str):
    path = os.path.join(RECEIPTS_DIR, f"{oid}.txt")
    if not os.path.exists(path):
        raise HTTPException(404, "receipt not ready")
    with open(path) as fh:
        return fh.read()
