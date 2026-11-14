#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
inplace_sed "s/^# 2026-11-14 tuning.*\n//; s/^DB_POOL_MAX=1$/DB_POOL_MAX=10/; s/^DB_POOL_TIMEOUT=0.5$/DB_POOL_TIMEOUT=3/" "$APP/.env"
dc up -d api >/dev/null 2>&1; sleep 8
