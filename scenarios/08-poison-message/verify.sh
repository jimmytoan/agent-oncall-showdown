#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "worker stays up for 30s" worker_stable 30
check restored "orders processed end to end" order_gets_receipt
check data "all 20 sentinel orders reached the database" test "$(psql_q "SELECT count(*) FROM orders WHERE id LIKE 'sentinel-%'")" = 20
check durable "poison message kept somewhere for analysis" bash -c "docker compose --project-directory '$APP' -f '$APP/compose.yaml' exec -T cache sh -c 'for k in \$(redis-cli --scan); do t=\$(redis-cli TYPE \$k); [ \"\$t\" = list ] && redis-cli LRANGE \$k 0 -1; [ \"\$t\" = string ] && redis-cli GET \$k; done' | grep -q LC-99812"
finish
