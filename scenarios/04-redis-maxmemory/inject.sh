#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
# Existing customer carts: ~3000 carts, ~6 MB. This is the data that must survive the incident.
note=$(printf 'x%.0s' $(seq 2000))
for i in $(seq 1 3000); do printf 'HSET cart:cust-%s 1 "{\\"product_id\\":1,\\"qty\\":1,\\"note\\":\\"%s\\"}"\n' "$i" "$note"; done \
  | dc exec -T cache redis-cli --pipe >/dev/null
# FinOps change: config file edited and hot-applied (no restart)
inplace_sed 's/^maxmemory 64mb$/# FinOps review 2026-11-13: right-size cache\nmaxmemory 3mb/' "$APP/cache/redis.conf"
redis_q CONFIG SET maxmemory 3mb >/dev/null
sleep 10
