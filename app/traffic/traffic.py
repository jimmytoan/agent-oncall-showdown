"""Synthetic customer traffic so incidents show up in logs and metrics like they would in production."""

import asyncio
import os
import random
import time

import httpx

TARGET = os.getenv("TARGET", "http://proxy/api")
CONCURRENCY = int(os.getenv("CONCURRENCY", "8"))

stats = {"ok": 0, "err": 0}


async def customer(client: httpx.AsyncClient, n: int) -> None:
    user = f"u{n}"
    while True:
        try:
            r = random.random()
            if r < 0.45:
                resp = await client.get(f"{TARGET}/products", params={"category": f"cat-{random.randint(0, 49)}"})
            elif r < 0.65:
                resp = await client.get(f"{TARGET}/products/{random.randint(1, 2_000_000)}")
            elif r < 0.80:
                resp = await client.post(
                    f"{TARGET}/cart/{user}",
                    json={"product_id": random.randint(1, 2_000_000), "qty": random.randint(1, 3), "note": "x" * 2000},
                )
            elif r < 0.90:
                resp = await client.get(f"{TARGET}/cart/{user}")
            else:
                items = [
                    {"product_id": random.randint(1, 2_000_000), "qty": random.randint(1, 3), "price": round(random.uniform(1, 300), 2)}
                    for _ in range(random.randint(1, 4))
                ]
                resp = await client.post(f"{TARGET}/orders", json={"user_id": user, "items": items})
            stats["ok" if resp.status_code < 500 else "err"] += 1
        except httpx.HTTPError:
            stats["err"] += 1
        await asyncio.sleep(random.uniform(0.05, 0.3))


async def reporter() -> None:
    while True:
        await asyncio.sleep(30)
        print(f"{time.strftime('%H:%M:%S')} traffic ok={stats['ok']} err={stats['err']}", flush=True)


async def main() -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        await asyncio.gather(reporter(), *(customer(client, i) for i in range(CONCURRENCY)))


if __name__ == "__main__":
    asyncio.run(main())
