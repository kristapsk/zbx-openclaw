#!/usr/bin/env bash
set -euo pipefail

url="${1:-http://127.0.0.1:18789/api/diagnostics/prometheus}"
token_file="${2:-/etc/zabbix/secrets/openclaw_gateway_token}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

body_file="$tmpdir/body"
header_file="$tmpdir/header"
http_status=0
metrics_present=0
curl_args=(
  --silent
  --show-error
  --output "$body_file"
  --max-time 10
  --write-out '%{http_code}'
)

# Token/password auth is optional. If the file is absent, try without a header;
# this supports gateways configured with auth mode "none" and keeps the check
# fail-soft when diagnostics-prometheus is not configured.
if [[ -r "$token_file" ]]; then
  token="$(tr -d '\r\n' < "$token_file")"
  if [[ -n "$token" ]]; then
    printf 'Authorization: Bearer %s\n' "$token" > "$header_file"
    chmod 0600 "$header_file"
    curl_args+=(--header "@$header_file")
  fi
fi

if status="$(curl "${curl_args[@]}" "$url" 2>/dev/null)"; then
  if [[ "$status" =~ ^[0-9]{3}$ ]]; then
    http_status="$((10#$status))"
  fi
fi

# Only pass the response through when it looks like OpenClaw Prometheus data.
# This prevents an HTML/JSON error response from poisoning dependent items.
if [[ "$http_status" -eq 200 ]] && \
   grep -Eq '^openclaw_[A-Za-z0-9_:]+(\{[^}]*\})?[[:space:]]+[-+0-9.eE]+' "$body_file" 2>/dev/null; then
  metrics_present=1
  cat "$body_file"
  printf '\n'
fi

# These synthetic metrics are always emitted, keeping the Zabbix master item
# and its dependent status items supported even when the plugin is absent.
printf '%s\n' \
  '# HELP zbx_openclaw_prometheus_available Whether the Prometheus endpoint returned HTTP 200.' \
  '# TYPE zbx_openclaw_prometheus_available gauge' \
  "zbx_openclaw_prometheus_available $([[ "$http_status" -eq 200 ]] && echo 1 || echo 0)" \
  '# HELP zbx_openclaw_prometheus_metrics_present Whether OpenClaw metrics were present in the response.' \
  '# TYPE zbx_openclaw_prometheus_metrics_present gauge' \
  "zbx_openclaw_prometheus_metrics_present $metrics_present" \
  '# HELP zbx_openclaw_prometheus_http_status HTTP status returned by the endpoint, or zero on a transport failure.' \
  '# TYPE zbx_openclaw_prometheus_http_status gauge' \
  "zbx_openclaw_prometheus_http_status $http_status"
