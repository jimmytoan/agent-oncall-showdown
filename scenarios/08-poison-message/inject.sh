#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
dc stop traffic >/dev/null   # quiet period so the sentinel orders queue up behind the poison deterministically
redis_q LPUSH orders '{"id":"7d1e0c52-legacy","user_id":"u-legacy-ios","items":null,"legacy_cart_ref":"LC-99812","client":"ios-3.2.0"}' >/dev/null
for i in $(seq 1 20); do
  redis_q LPUSH orders "{\"id\":\"sentinel-$i\",\"user_id\":\"vip-$i\",\"items\":[{\"product_id\":$i,\"qty\":1,\"price\":10.0}]}" >/dev/null
done
dc start traffic >/dev/null
sleep 30
