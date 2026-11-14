#!/usr/bin/env bash
# Reference fix (what a careful human would do). Used to self-test the scenario.
source "$(dirname "$0")/../_lib.sh"
inplace_sed "s/^\s*# platform std ports.*\n//; s/reverse_proxy api:8080/reverse_proxy api:8000/" "$APP/proxy/Caddyfile"
dc exec -T proxy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1
