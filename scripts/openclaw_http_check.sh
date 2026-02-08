#!/usr/bin/env bash
set -euo pipefail

url="${1:-http://127.0.0.1:18789/health}"

code="$(curl -sS -o /dev/null -m 5 -w '%{http_code}' "$url" || true)"
[[ "$code" == "200" ]] && echo 1 || echo 0

