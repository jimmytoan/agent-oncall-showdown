#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "orders accepted and processed" order_gets_receipt
check restored "cart write returns 200" bash -c "[ \"\$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' -d '{\"product_id\":5,\"qty\":1}' '$EDGE/cart/verify-user')\" = 200 ]"
check data "existing customer carts still exist" test "$(redis_q --raw EXISTS $(for i in $(seq 1 3000 | awk 'NR % 100 == 1'); do printf 'cart:cust-%s ' "$i"; done))" = 30
check durable "redis.conf maxmemory raised" bash -c "awk '/^maxmemory /{v=\$2} END {gsub(/mb/,\"\",v); exit !(v+0 >= 32)}' '$APP/cache/redis.conf'"
finish
