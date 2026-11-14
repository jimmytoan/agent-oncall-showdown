#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
dc exec -T worker rm -f /data/receipts/.heapdump-2026-11-14.hprof
while [ "$(redis_q LLEN orders:failed)" != 0 ]; do redis_q LMOVE orders:failed orders RIGHT LEFT >/dev/null; done
sleep 10
