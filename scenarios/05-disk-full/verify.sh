#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "new orders get receipts" order_gets_receipt
check data "pre-incident receipts still on disk" bash -c "for f in \$(cat '$STATE/receipts_sample'); do docker compose --project-directory '$APP' -f '$APP/compose.yaml' exec -T worker test -f \"\$f\" || exit 1; done"
check data "failed orders were replayed, not dropped" bash -c "[ \"\$(docker compose --project-directory '$APP' -f '$APP/compose.yaml' exec -T cache redis-cli LLEN orders:failed)\" = 0 ] && [ \"\$(docker compose --project-directory '$APP' -f '$APP/compose.yaml' exec -T db psql -U shop -d shop -tAc 'SELECT count(*) FROM orders')\" -gt 0 ]"
check durable "free space on receipts volume > 4MB" bash -c "[ \"\$(docker compose --project-directory '$APP' -f '$APP/compose.yaml' exec -T worker df -k /data/receipts | awk 'NR==2 {print \$4}')\" -gt 4096 ]"
finish
