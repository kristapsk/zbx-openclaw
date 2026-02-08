#!/usr/bin/env bash
set -euo pipefail

url="${1:-http://127.0.0.1:18789/health}"

t="$(curl -sS -o /dev/null -m 5 -w '%{time_total}' "$url" || echo 0)"

# Split seconds and fractional part
sec="${t%.*}"
frac="${t#*.}"

# Pad or trim fraction to milliseconds
ms="${frac}000"
ms="${ms:0:3}"

echo $(( sec * 1000 + ms ))

