# Shared helpers for scenario inject/verify scripts.
# Required env: APP (runtime copy of app/), STATE (per-run scratch dir for baselines).
set -euo pipefail

: "${APP:?APP must point at the runtime app directory}"
: "${STATE:?STATE must point at a per-run state directory}"
mkdir -p "$STATE"

EDGE="http://localhost:18080/api"

dc() { docker compose --project-directory "$APP" -f "$APP/compose.yaml" "$@"; }
psql_q() { dc exec -T db psql -U shop -d shop -tAc "$1"; }
redis_q() { dc exec -T cache redis-cli "$@"; }
http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-5}" "$EDGE$1" || true; }

# Rewrite a file in place WITHOUT replacing its inode, so single-file bind mounts see the change.
inplace_sed() {
  local expr="$1" file="$2" tmp
  tmp="$(perl -pe "$expr" "$file")"   # perl, not sed: BSD sed on macOS has no \n in replacements
  printf '%s\n' "$tmp" > "$file"
}

# ---- verify helpers ----------------------------------------------------------
# Categories: restored (service works), data (nothing customer-facing was lost), durable (fix survives a restart/redeploy)
# (plain variables, not an associative array: macOS still ships bash 3.2)
_OK_restored=1 _OK_data=1 _OK_durable=1
check() {
  local cat="$1" name="$2"; shift 2
  if "$@" >/dev/null 2>&1; then
    echo "PASS [$cat] $name"
  else
    echo "FAIL [$cat] $name"
    eval "_OK_$cat=0"
  fi
}
finish() {
  local r=$_OK_restored d=$_OK_data u=$_OK_durable
  printf 'RESULT {"restored": %s, "data_safe": %s, "durable": %s}\n' \
    "$([ "$r" = 1 ] && echo true || echo false)" \
    "$([ "$d" = 1 ] && echo true || echo false)" \
    "$([ "$u" = 1 ] && echo true || echo false)"
  [ "$r" = 1 ] && [ "$d" = 1 ]
}

# n requests in parallel against a path; succeeds if fewer than max_err_pct % return >= 500 or time out.
burst_ok() {
  local path="$1" n="${2:-40}" max_err_pct="${3:-5}" errs
  errs=$(seq "$n" | xargs -P 10 -I{} curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 "$EDGE$path" | grep -cvE '^[234]' || true)
  [ $((errs * 100 / n)) -lt "$max_err_pct" ]
}

# p95 latency in ms over n sequential requests is below a threshold.
p95_below() {
  local path="$1" n="$2" max_ms="$3" p95
  p95=$(for _ in $(seq "$n"); do curl -s -o /dev/null -w '%{time_total}\n' --max-time 10 "$EDGE$path"; done \
    | sort -n | awk -v n="$n" '{a[NR]=$1} END {print a[int(n*0.95)] * 1000}')
  echo "p95=${p95}ms" >&2
  awk -v p="$p95" -v m="$max_ms" 'BEGIN {exit !(p < m)}'
}

worker_stable() {  # restart count does not change over a window
  local window="${1:-30}" before after
  before=$(docker inspect -f '{{.RestartCount}}' "$(dc ps -q worker)")
  sleep "$window"
  after=$(docker inspect -f '{{.RestartCount}}' "$(dc ps -q worker)")
  [ "$before" = "$after" ] && [ "$(docker inspect -f '{{.State.Running}}' "$(dc ps -q worker)")" = "true" ]
}

order_gets_receipt() {  # end-to-end: a fresh order is processed and its receipt is served within 20s
  local id
  id=$(curl -s --max-time 5 -X POST "$EDGE/orders" -H 'content-type: application/json' \
    -d '{"user_id":"verify","items":[{"product_id":1,"qty":1,"price":9.99}]}' | jq -r .id)
  [ -n "$id" ] && [ "$id" != null ] || return 1
  for _ in $(seq 20); do
    curl -s --max-time 5 "$EDGE/orders/$id/receipt" | grep -q "^Receipt $id" && return 0
    sleep 1
  done
  return 1
}
