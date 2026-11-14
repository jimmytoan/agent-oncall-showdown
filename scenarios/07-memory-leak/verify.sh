#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "worker stays up for 60s" worker_stable 60
check restored "orders processed end to end" order_gets_receipt
check data "orders table kept its rows" test "$(psql_q 'SELECT count(*) FROM orders')" -ge "$(cat "$STATE/orders_baseline")"
check durable "RECEIPT_CACHE disabled in .env" bash -c "grep -E '^RECEIPT_CACHE=' '$APP/.env' | tail -1 | grep -q '=off'"
finish
