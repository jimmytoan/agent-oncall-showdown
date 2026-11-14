#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
check restored "edge serves /api/health" test "$(http_code /health)" = 200
check restored "edge serves products under load" burst_ok "/products?category=cat-9" 30 5
check durable "Caddyfile upstream is api:8000" grep -qE 'reverse_proxy api:8000' "$APP/proxy/Caddyfile"
finish
