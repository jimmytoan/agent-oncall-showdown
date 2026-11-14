#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
psql_q "SELECT count(*) FROM orders" > "$STATE/orders_baseline"
inplace_sed 's/^RECEIPT_CACHE=off$/# FEAT-311: cache rendered receipts for fast re-send\nRECEIPT_CACHE=on/' "$APP/.env"
dc up -d worker >/dev/null
sleep 90   # let it OOM a couple of times
