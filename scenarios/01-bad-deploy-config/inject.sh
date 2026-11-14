#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
psql_q "SELECT count(*) FROM orders" > "$STATE/orders_baseline"
inplace_sed 's/^DB_HOST=db$/# CHG-4821 2026-11-14: point at managed primary\nDB_HOST=db-primary.internal/' "$APP/.env"
dc up -d api worker >/dev/null
