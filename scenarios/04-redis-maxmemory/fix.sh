#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
redis_q CONFIG SET maxmemory 64mb >/dev/null
inplace_sed "s/^maxmemory 3mb$/maxmemory 64mb/" "$APP/cache/redis.conf"
