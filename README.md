# OpenClaw Zabbix Monitoring

Zabbix 7.4 template for monitoring a locally running OpenClaw Gateway with
**Zabbix agent2 active checks**.

The template does not depend on systemd or any particular OpenClaw process
manager. It uses:

- the built-in `net.tcp.listen[]` key for the local TCP listener;
- two small local scripts for the `/health` HTTP check and its latency;
- an optional local Prometheus collector for richer OpenClaw diagnostics.

The basic TCP and HTTP checks continue to work when the OpenClaw
`diagnostics-prometheus` plugin is not installed or enabled.

## Repository layout

```text
.
├── README.md
├── Template_OpenClaw_Gateway_Agent2.yaml
├── scripts
│   ├── openclaw_http_check.sh
│   ├── openclaw_http_latency_ms.sh
│   └── openclaw_prometheus.sh
└── zabbix_agent2.d
    └── openclaw.conf
```

## What is monitored

### Basic monitoring

| Signal | Method | Default |
|---|---|---|
| Gateway TCP listener | Built-in active agent item `net.tcp.listen[]` | Port `18789` |
| HTTP health | Local `curl` script | `http://127.0.0.1:18789/health` |
| HTTP health latency | Local `curl` and `awk` script | Warning above `500 ms` average |

OpenClaw documents `/health` as its lightweight HTTP liveness endpoint. It
returns HTTP 200 and a small JSON response when the Gateway is live.

### Optional Prometheus monitoring

When the official `diagnostics-prometheus` plugin is enabled, the template also
collects aggregate metrics for:

- completed and failed runs;
- model calls, errors and failovers;
- input/output tokens and model cost;
- tool executions, errors and blocked calls;
- message processing and delivery errors;
- queue depth and stuck sessions;
- liveness warnings;
- RSS memory and memory-pressure events;
- dropped Prometheus series and diagnostic events;
- telemetry exporter errors.

The Prometheus collector fetches the protected endpoint locally and sends one
text document to Zabbix. Dependent items use native Zabbix Prometheus
preprocessing, so the endpoint is fetched only once per interval.

## Requirements

- Zabbix server 7.4
- Zabbix agent2 on the monitored host
- active agent checks configured
- `curl`
- `awk`
- OpenClaw Gateway reachable locally, normally on `127.0.0.1:18789`

## Install the agent-side files

Run from a checkout of this repository on the monitored host:

```bash
sudo install -d -m 0755 /etc/zabbix/scripts
sudo install -m 0755 scripts/openclaw_http_check.sh \
  /etc/zabbix/scripts/openclaw_http_check.sh
sudo install -m 0755 scripts/openclaw_http_latency_ms.sh \
  /etc/zabbix/scripts/openclaw_http_latency_ms.sh
sudo install -m 0755 scripts/openclaw_prometheus.sh \
  /etc/zabbix/scripts/openclaw_prometheus.sh

sudo install -d -m 0755 /etc/zabbix/zabbix_agent2.d
sudo install -m 0644 zabbix_agent2.d/openclaw.conf \
  /etc/zabbix/zabbix_agent2.d/openclaw.conf
```

The installed UserParameters are:

```conf
UserParameter=openclaw.http.health[*],/etc/zabbix/scripts/openclaw_http_check.sh "$1"
UserParameter=openclaw.http.latency_ms[*],/etc/zabbix/scripts/openclaw_http_latency_ms.sh "$1"
UserParameter=openclaw.prometheus[*],/etc/zabbix/scripts/openclaw_prometheus.sh "$1" "$2"
```

Confirm that the agent2 main configuration includes the directory. Packaged
configurations normally already do:

```conf
Include=/etc/zabbix/zabbix_agent2.d/*.conf
```

For active checks, also configure the correct server or proxy and use exactly
the same host name as in the Zabbix frontend:

```conf
ServerActive=zabbix.example.net
Hostname=openclaw-host.example.net
```

Validate and restart agent2:

```bash
sudo zabbix_agent2 -T
sudo systemctl restart zabbix-agent2
```

If agent2 is managed without systemd, restart it using the host's normal service
manager. The OpenClaw template itself has no systemd dependency.

## Import and link the template

1. In Zabbix, open **Data collection -> Templates**.
2. Import `Template_OpenClaw_Gateway_Agent2.yaml`.
3. Link **Template App OpenClaw Gateway** to the OpenClaw host.
4. Override macros on the host when its address, port, paths or thresholds differ.

The template uses active agent item type `ZABBIX_ACTIVE`; agent2 executes the
TCP and UserParameter checks on the monitored host.

## Template macros

| Macro | Default | Purpose |
|---|---:|---|
| `{$OPENCLAW_HOST}` | `127.0.0.1` | Host used by local HTTP checks |
| `{$OPENCLAW_PORT}` | `18789` | Gateway TCP port |
| `{$OPENCLAW_HEALTH_PATH}` | `/health` | Basic liveness path |
| `{$OPENCLAW_LATENCY_WARN_MS}` | `500` | Five-minute average latency warning |
| `{$OPENCLAW_PROMETHEUS_PATH}` | `/api/diagnostics/prometheus` | Optional metrics endpoint |
| `{$OPENCLAW_PROMETHEUS_TOKEN_FILE}` | `/etc/zabbix/secrets/openclaw_gateway_token` | Bearer credential file |
| `{$OPENCLAW_PROMETHEUS_INTERVAL}` | `1m` | Optional metrics collection interval |
| `{$OPENCLAW_PROMETHEUS_REQUIRED}` | `0` | Set to `1` to alert when telemetry is unavailable or empty |
| `{$OPENCLAW_MODEL_ERRORS_WARN}` | `3` | Model errors in ten minutes |
| `{$OPENCLAW_MODEL_FAILOVERS_WARN}` | `3` | Model failovers in fifteen minutes |
| `{$OPENCLAW_TOOL_ERRORS_WARN}` | `5` | Tool errors in ten minutes |
| `{$OPENCLAW_TOOL_BLOCKED_WARN}` | `3` | Blocked tools in ten minutes |
| `{$OPENCLAW_MESSAGE_ERRORS_WARN}` | `5` | Message errors in ten minutes |
| `{$OPENCLAW_QUEUE_DEPTH_WARN}` | `10` | Session queue depth warning |
| `{$OPENCLAW_STUCK_SESSIONS_WARN}` | `2` | Stuck-session events in fifteen minutes |
| `{$OPENCLAW_LIVENESS_WARNINGS_WARN}` | `5` | Liveness warnings in fifteen minutes |
| `{$OPENCLAW_MEMORY_PRESSURE_WARN}` | `2` | Memory-pressure events in fifteen minutes |
| `{$OPENCLAW_COST_DAILY_WARN_USD}` | `0` | Daily cost warning; zero disables it |


### Alert noise control

Prometheus event counters are intentionally not alerted on every single event.
The default thresholds require several events within a 10- or 15-minute window
before creating a problem. Liveness warnings and blocked-tool events are
informational by default; memory-pressure and stuck-session events use Average
severity.

Counter-based triggers also require
`openclaw.prometheus.metrics_present=1` continuously for the complete trigger
window. This prevents false positives after the diagnostics plugin starts,
restarts or becomes reachable again, when a real cumulative counter replaces
the collector's temporary fallback value of zero.

Override the threshold macros per host if a particular OpenClaw workload needs
stricter or looser alerting.

## Verify the basic checks

Run on the monitored host:

```bash
zabbix_agent2 -t 'net.tcp.listen[18789]'
zabbix_agent2 -t 'openclaw.http.health["http://127.0.0.1:18789/health"]'
zabbix_agent2 -t 'openclaw.http.latency_ms["http://127.0.0.1:18789/health"]'
```

Expected results while OpenClaw is healthy:

- TCP listener: `1`
- HTTP health: `1`
- HTTP latency: a non-negative integer in milliseconds

The latency script returns `0` when the HTTP request fails. The separate health
item is the authoritative failure signal, and the latency trigger is evaluated
only while health is successful.

## Optional: enable diagnostics-prometheus in OpenClaw

OpenClaw's official plugin exposes Prometheus text format at:

```text
GET /api/diagnostics/prometheus
```

The route uses Gateway operator authentication and must not be exposed as a
public unauthenticated metrics endpoint.

Install and enable the plugin as the OpenClaw user:

```bash
openclaw plugins install clawhub:@openclaw/diagnostics-prometheus
openclaw plugins enable diagnostics-prometheus
openclaw config set diagnostics.enabled true
openclaw gateway restart
```

The route is registered at plugin startup, so the Gateway must be restarted
after enabling it.

Official reference:

- <https://docs.openclaw.ai/gateway/prometheus>

## Configure the Gateway credential for Zabbix

The Prometheus diagnostics endpoint is protected by the Gateway authentication token. The monitoring script reads this token from a local file that is accessible to the `zabbix` user.

If your Gateway is already configured, you **do not need to generate a new token**.

First, verify that a Gateway token exists:

```bash
jq -e '.gateway.auth.token | type == "string" and length > 0' \
  ~/.openclaw/openclaw.json >/dev/null \
  && echo "Gateway token found"
```

Alternatively, you can run:

```bash
openclaw config get gateway.auth.token
```

This command intentionally **does not reveal the token** and prints `__OPENCLAW_REDACTED__` when a token is configured.

If no token exists, generate one according to the OpenClaw documentation and restart the Gateway.

### Install the token for Zabbix

Copy the configured Gateway token into a file readable by the `zabbix` user:

```bash
sudo install -d -o root -g zabbix -m 0750 /etc/zabbix/secrets

jq -r '.gateway.auth.token' ~/.openclaw/openclaw.json \
  | sudo tee /etc/zabbix/secrets/openclaw_gateway_token >/dev/null

sudo chown root:zabbix /etc/zabbix/secrets/openclaw_gateway_token
sudo chmod 0640 /etc/zabbix/secrets/openclaw_gateway_token
```

Verify that the `zabbix` user can read the file:

```bash
sudo -u zabbix test -s /etc/zabbix/secrets/openclaw_gateway_token \
  && echo "Zabbix can read the token"
```

### Enable Prometheus diagnostics (optional)

If you want to collect Prometheus telemetry, enable the plugin and restart the Gateway:

```bash
openclaw plugins enable diagnostics-prometheus
openclaw gateway restart
```

### Verify the endpoint

Run the following command as the `zabbix` user:

```bash
sudo -u zabbix sh -c '
  token=$(cat /etc/zabbix/secrets/openclaw_gateway_token)
  curl -fsS \
    -H "Authorization: Bearer ${token}" \
    http://127.0.0.1:18789/api/diagnostics/prometheus \
    | head
'
```

A successful response should begin with Prometheus metrics whose names start with `openclaw_`.

If the `diagnostics-prometheus` plugin is not installed or enabled, the endpoint will return **404 Not Found**. This is expected, and the basic TCP and `/health` monitoring provided by this template will continue to work normally.



## Verify optional Prometheus collection

First test the OpenClaw endpoint directly:

```bash
TOKEN_FILE=/etc/zabbix/secrets/openclaw_gateway_token
curl --silent --show-error \
  --header "Authorization: Bearer $(cat "$TOKEN_FILE")" \
  http://127.0.0.1:18789/api/diagnostics/prometheus | head
```

Then run the collector as the Zabbix user:

```bash
sudo -u zabbix /etc/zabbix/scripts/openclaw_prometheus.sh \
  http://127.0.0.1:18789/api/diagnostics/prometheus \
  /etc/zabbix/secrets/openclaw_gateway_token | tail -n 12
```

A working endpoint with telemetry should end with synthetic status metrics like:

```text
zbx_openclaw_prometheus_available 1
zbx_openclaw_prometheus_metrics_present 1
zbx_openclaw_prometheus_http_status 200
```

You can also test the UserParameter:

```bash
zabbix_agent2 -t 'openclaw.prometheus["http://127.0.0.1:18789/api/diagnostics/prometheus","/etc/zabbix/secrets/openclaw_gateway_token"]'
```

## Behavior when diagnostics-prometheus is absent

The optional collector is deliberately fail-soft:

- plugin missing, normally HTTP 404: endpoint available `0`, metrics present `0`;
- missing or wrong credential, normally HTTP 401/403: endpoint available `0`;
- transport failure: HTTP status `0`;
- `diagnostics.enabled=false`: endpoint may return HTTP 200 but no metrics;
- absent OpenClaw metric series: dependent item receives `0` through custom
  preprocessing failure handling.

The Prometheus raw item remains supported because the collector always emits
valid synthetic metrics. All telemetry-based alert expressions are gated by
`openclaw.prometheus.metrics_present=1`.

By default, `{$OPENCLAW_PROMETHEUS_REQUIRED}=0`, so the absence of the plugin
creates no Prometheus availability problem. The original TCP, HTTP health and
latency checks continue normally.

Set this host macro to require the plugin and alert on its absence:

```text
{$OPENCLAW_PROMETHEUS_REQUIRED}=1
```

## Security notes

- Keep the Gateway bound to loopback unless remote exposure is intentionally
  configured and protected.
- Do not expose `/api/diagnostics/prometheus` publicly.
- The collector reads the credential from a root-owned, group-readable file.
- The script passes the Authorization header to `curl` through a temporary
  header file instead of placing the secret directly in the `curl` process
  argument list.
- The temporary directory and header file are removed on exit.
- The raw Prometheus master item has history disabled, so the complete
  exposition document is not retained in the Zabbix database.
- OpenClaw Prometheus metrics intentionally omit prompt text, responses, tool
  payloads, raw session identifiers and secrets.

## Troubleshooting

### Basic health works, Prometheus status is 404

The plugin is not installed/enabled or the Gateway was not restarted after it
was enabled. Basic monitoring is unaffected.

### Prometheus status is 401 or 403

Check the credential file and the Gateway authentication mode:

```bash
sudo -u zabbix test -r /etc/zabbix/secrets/openclaw_gateway_token
openclaw config get gateway.auth.mode
openclaw config get gateway.auth.token
```

Restart agent2 after correcting permissions or changing the UserParameter.

### Prometheus status is 200 but metrics present is 0

Check that diagnostics are enabled:

```bash
openclaw config get diagnostics.enabled
```

OpenClaw documents that the route can remain registered while returning no
diagnostic events when diagnostics are disabled.

### Dependent metrics remain zero

Generate some OpenClaw activity, then inspect the raw endpoint. Many counters
do not appear until the corresponding event has happened at least once.

### Agent item is unsupported

Validate the agent configuration and execute the script as the `zabbix` user:

```bash
sudo zabbix_agent2 -T
sudo -u zabbix /etc/zabbix/scripts/openclaw_http_check.sh \
  http://127.0.0.1:18789/health
sudo -u zabbix /etc/zabbix/scripts/openclaw_prometheus.sh \
  http://127.0.0.1:18789/api/diagnostics/prometheus \
  /etc/zabbix/secrets/openclaw_gateway_token
```

## Notes on aggregation

This template intentionally aggregates labelled Prometheus series into a small
set of operational totals. It does not perform low-level discovery for every
provider, model, agent, channel or tool label. This limits item count and avoids
high-cardinality Zabbix configurations while still providing useful alerts.

OpenClaw caps retained Prometheus series and exposes
`openclaw_prometheus_series_dropped_total`. The template monitors that counter
because an increase indicates that new series are being discarded.

## References

- OpenClaw Prometheus metrics: <https://docs.openclaw.ai/gateway/prometheus>
- OpenClaw health checks: <https://docs.openclaw.ai/gateway/health>
- Zabbix 7.4 Prometheus checks:
  <https://www.zabbix.com/documentation/7.4/en/manual/config/items/itemtypes/http/prometheus>
- Zabbix 7.4 template import/export format:
  <https://www.zabbix.com/documentation/7.4/en/manual/xml_export_import/templates>
