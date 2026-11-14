"""shopfront worker: takes orders off the Redis queue, stores them in Postgres, writes a receipt file."""

import json
import logging
import os
import time

import psycopg
import redis

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s worker %(message)s",
)
log = logging.getLogger("worker")

DSN = (
    f"host={os.environ['DB_HOST']} port={os.getenv('DB_PORT', '5432')} "
    f"dbname={os.environ['DB_NAME']} user={os.environ['DB_USER']} "
    f"password={os.environ['DB_PASSWORD']} connect_timeout=2"
)
RECEIPTS_DIR = os.getenv("RECEIPTS_DIR", "/data/receipts")
RECEIPT_CACHE = os.getenv("RECEIPT_CACHE", "off") == "on"

rds = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

# Feature flag RECEIPT_CACHE keeps rendered receipts in memory "for fast re-sends".
# It is never evicted - that's the bug.
_receipt_cache: list[bytes] = []


def render_receipt(order: dict, total: float) -> str:
    lines = [f"Receipt {order['id']}", f"Customer {order['user_id']}"]
    for item in order["items"]:
        lines.append(f"  {item['qty']} x product {item['product_id']} @ {item['price']:.2f}")
    lines.append(f"Total {total:.2f}")
    return "\n".join(lines) + "\n"


def process(conn: psycopg.Connection, raw: str) -> None:
    order = json.loads(raw)
    total = sum(i["qty"] * i["price"] for i in order["items"])
    conn.execute(
        "INSERT INTO orders (id, user_id, items, total) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
        (order["id"], order["user_id"], json.dumps(order["items"]), total),
    )
    conn.commit()
    text = render_receipt(order, total)
    path = os.path.join(RECEIPTS_DIR, f"{order['id']}.txt")
    try:
        with open(path, "w") as fh:
            fh.write(text)
    except OSError as exc:
        log.error("failed to write receipt for order %s: %s", order["id"], exc)
        if os.path.exists(path):
            os.remove(path)  # never leave a truncated receipt behind
        rds.lpush("orders:failed", raw)
        return
    if RECEIPT_CACHE:
        _receipt_cache.append(text.encode() * 5000)  # ~1 MB per order, never released
    log.info("processed order %s total=%.2f", order["id"], total)


def main() -> None:
    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    conn = psycopg.connect(DSN)
    # Crash recovery: anything left in-flight from a previous run is retried first.
    stuck = rds.lrange("orders:processing", 0, -1)
    if stuck:
        log.warning("recovering %d in-flight order(s) from previous run", len(stuck))
    for raw in reversed(stuck):
        process(conn, raw)
        rds.lrem("orders:processing", 1, raw)
    log.info("worker started receipt_cache=%s", RECEIPT_CACHE)
    while True:
        raw = rds.blmove("orders", "orders:processing", timeout=5, src="RIGHT", dest="LEFT")
        if raw is None:
            continue
        process(conn, raw)  # an exception here crashes the worker; the order stays in orders:processing
        rds.lrem("orders:processing", 1, raw)


if __name__ == "__main__":
    while True:
        try:
            main()
        except (psycopg.OperationalError, redis.exceptions.ConnectionError) as exc:
            log.error("dependency unavailable, retrying in 2s: %s", exc)
            time.sleep(2)
