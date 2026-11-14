#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
psql_q "SELECT count(*) FROM orders" > "$STATE/orders_baseline"
inplace_sed 's/^DB_POOL_MAX=10$/# 2026-11-14 tuning: reduce DB connections\nDB_POOL_MAX=1/; s/^DB_POOL_TIMEOUT=3$/DB_POOL_TIMEOUT=0.5/' "$APP/.env"
dc up -d api >/dev/null
