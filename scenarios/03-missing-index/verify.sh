#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "products p95 under 150ms" p95_below "/products?category=cat-11" 20 150
check data "no products deleted" test "$(psql_q 'SELECT count(*) FROM products')" = "$(cat "$STATE/products_baseline")"
check durable "an index covers products.category" bash -c "[ \"\$(docker compose --project-directory '$APP' -f '$APP/compose.yaml' exec -T db psql -U shop -d shop -tAc \"SELECT count(*) FROM pg_indexes WHERE tablename='products' AND indexdef ILIKE '%(category%'\")\" -ge 1 ]"
finish
