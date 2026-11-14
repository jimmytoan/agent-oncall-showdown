#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
inplace_sed 's/reverse_proxy api:8000/# platform std ports rollout PLAT-77\n\t\treverse_proxy api:8080/' "$APP/proxy/Caddyfile"
for _ in 1 2 3; do dc exec -T proxy caddy reload --config /etc/caddy/Caddyfile >/dev/null && break; sleep 2; done
