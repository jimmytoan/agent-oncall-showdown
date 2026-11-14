#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "product detail survives concurrency" burst_ok "/products/42" 40 5
check restored "product list survives concurrency" burst_ok "/products?category=cat-7" 40 5
check data "orders table kept its rows" test "$(psql_q 'SELECT count(*) FROM orders')" -ge "$(cat "$STATE/orders_baseline")"
check durable ".env pool size raised" bash -c "grep -E '^DB_POOL_MAX=' '$APP/.env' | tail -1 | awk -F= '\$2 >= 5 {ok=1} END {exit !ok}'"
finish
