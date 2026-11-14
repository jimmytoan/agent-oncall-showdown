#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "products endpoint healthy" burst_ok "/products?category=cat-3" 30 5
check restored "orders flow end to end" order_gets_receipt
check data "orders table kept its rows" test "$(psql_q 'SELECT count(*) FROM orders')" -ge "$(cat "$STATE/orders_baseline")"
check durable ".env no longer points at db-primary.internal" bash -c "! grep -q '^DB_HOST=db-primary' '$APP/.env'"
finish
