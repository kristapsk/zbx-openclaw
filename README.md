# OpenClaw Zabbix Monitoring (agent2, local HTTP)

This setup provides **lightweight, portable monitoring** for a locally running OpenClaw gateway using **Zabbix agent2**.

---

## What is monitored

| Signal | How | Where it runs |
|------|----|---------------|
| TCP port listening | `net.tcp.listen[]` | Zabbix agent (active) on host |
| HTTP health (200 OK) | curl script | Zabbix agent (active) on host |
| HTTP latency (ms) | curl script | Zabbix agent (active) on host |

---

## Default assumptions

These are **defaults only** and can be overridden per host:

- OpenClaw gateway listens on `127.0.0.1:18789`
- Health endpoint is `/health`
- HTTP 200 means healthy

---

## Zabbix template

Import the provided template:

```
Template_OpenClaw_Gateway.yaml
```

### Template macros

| Macro | Default | Description |
|-----|--------|-------------|
| `{$OPENCLOW_HOST}` | `127.0.0.1` | Host/interface used for local HTTP checks |
| `{$OPENCLOW_PORT}` | `18789` | OpenClaw gateway TCP port |
| `{$OPENCLOW_HEALTH_PATH}` | `/health` | HTTP health endpoint path |
| `{$OPENCLOW_LATENCY_WARN_MS}` | `500` | Warning threshold for latency |

Health URL is constructed as:

```
http://{$OPENCLOW_HOST}:{$OPENCLOW_PORT}{$OPENCLOW_HEALTH_PATH}
```

---

## Agent-side configuration

### 1. UserParameters

Create:

```
/etc/zabbix/zabbix_agent2.d/openclaw.conf
```

```
UserParameter=openclaw.http.health[*],/etc/zabbix/scripts/openclaw_http_check.sh "$1"
UserParameter=openclaw.http.latency_ms[*],/etc/zabbix/scripts/openclaw_http_latency_ms.sh "$1"
```

Restart agent:

```
systemctl restart zabbix-agent2
```

---

### 2. Scripts

Copy the provided scripts to the monitored host, to `/etc/zabbix/scripts/`.

Set permissions:

```
chown root:root /etc/zabbix/scripts/openclaw_http_*.sh
chmod 0755 /etc/zabbix/scripts/openclaw_http_*.sh
systemctl restart zabbix-agent2
```

---

## Local validation

Run on the monitored host:

```
zabbix_agent2 -t 'net.tcp.listen[18789]'
zabbix_agent2 -t 'openclaw.http.health[http://127.0.0.1:18789/health]'
zabbix_agent2 -t 'openclaw.http.latency_ms[http://127.0.0.1:18789/health]'
```

Expected:
- TCP: `1`
- Health: `1`
- Latency: integer value in ms

---

## Why HTTP checks use scripts

Zabbix **HTTP agent items always run on the server or proxy**, not on the monitored host.  
Because OpenClaw typically binds to `127.0.0.1`, server-side HTTP checks cannot reach it.

Using **agent-executed scripts** is the correct and supported way to:
- perform local HTTP checks
- keep endpoints private
- avoid exposing health ports externally

---

## Summary

This setup provides **robust, low-maintenance monitoring** for OpenClaw with a correct execution model and minimal operational overhead.
