#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
redis_q LMOVE orders:processing orders:dead-letter RIGHT LEFT >/dev/null
sleep 15
