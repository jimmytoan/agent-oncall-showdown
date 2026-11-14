#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
inplace_sed "s/^# FEAT-311.*\n//; s/^RECEIPT_CACHE=on$/RECEIPT_CACHE=off/" "$APP/.env"
dc up -d worker >/dev/null 2>&1; sleep 10
