#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
psql_q "SELECT count(*) FROM products" > "$STATE/products_baseline"
psql_q "DROP INDEX products_category_price_idx" >/dev/null
