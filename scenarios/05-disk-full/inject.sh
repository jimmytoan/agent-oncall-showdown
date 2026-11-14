#!/usr/bin/env bash
source "$(dirname "$0")/../_lib.sh"
dc exec -T worker sh -c 'ls /data/receipts/*.txt | head -50' > "$STATE/receipts_sample"
# A stray heap dump grows until the volume is full (dd stops at ENOSPC)
dc exec -T worker sh -c 'dd if=/dev/zero of=/data/receipts/.heapdump-2026-11-14.hprof bs=64k 2>/dev/null; true'
sleep 15
