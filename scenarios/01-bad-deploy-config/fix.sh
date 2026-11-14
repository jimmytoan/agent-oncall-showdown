#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
inplace_sed "s/^# CHG-4821.*\n//; s/^DB_HOST=db-primary.internal$/DB_HOST=db/" "$APP/.env"
dc up -d api worker >/dev/null 2>&1; sleep 8
