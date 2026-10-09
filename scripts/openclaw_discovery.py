#!/usr/bin/env python3
"""Emit Zabbix LLD JSON for extra OpenClaw Gateway instances.

The default (single) instance is still monitored by the template's static
items and macros. This script is only for additional instances.

Missing, empty, or unreadable file -> [].
"""

from __future__ import annotations

import json
import re
import sys

DEFAULT_FILE = "/etc/zabbix/openclaw.instances.json"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
PATH_RE = re.compile(r"^/[A-Za-z0-9._+/-]*$")
HOST_RE = re.compile(r"^[A-Za-z0-9._:-]+$")


def fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    try:
        raw = open(path, encoding="utf-8").read().strip()
    except FileNotFoundError:
        print("[]")
        return
    except OSError:
        print("[]")
        return

    if not raw:
        print("[]")
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")

    if isinstance(data, dict) and isinstance(data.get("data"), list):
        rows = data["data"]
    elif isinstance(data, list):
        rows = data
    else:
        fail(f'{path} must be a JSON array or {{"data": [...]}}')

    out = []
    seen_names: set[str] = set()
    seen_ports: set[str] = set()

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail(f"entry {index} is not an object")

        name = row.get("{#NAME}", row.get("name"))
        port = row.get("{#PORT}", row.get("port"))
        if name is None or port is None:
            fail(f"entry {index} needs name/port")

        name = str(name).strip()
        port_s = str(port).strip()
        if not NAME_RE.match(name):
            fail(f"invalid name {name!r} (use A-Za-z0-9._-)")
        if not port_s.isdigit() or not (1 <= int(port_s) <= 65535):
            fail(f"invalid port {port_s!r}")

        token = str(row.get("{#TOKEN_FILE}", row.get("token_file", ""))).strip()
        if not token:
            token = f"/etc/zabbix/secrets/openclaw_{name}_token"
        if not PATH_RE.match(token):
            fail(f"invalid token_file {token!r}")

        host = str(row.get("{#HOST}", row.get("host", "127.0.0.1"))).strip()
        if not HOST_RE.match(host):
            fail(f"invalid host {host!r}")

        health = str(row.get("{#HEALTH_PATH}", row.get("health_path", "/health"))).strip()
        prom = str(
            row.get(
                "{#PROMETHEUS_PATH}",
                row.get("prometheus_path", "/api/diagnostics/prometheus"),
            )
        ).strip()
        if not PATH_RE.match(health) or not PATH_RE.match(prom):
            fail("invalid health_path or prometheus_path")

        key = name.lower()
        if key in seen_names:
            fail(f"duplicate name {name!r}")
        if port_s in seen_ports:
            fail(f"duplicate port {port_s}")
        seen_names.add(key)
        seen_ports.add(port_s)

        out.append(
            {
                "{#NAME}": name,
                "{#PORT}": port_s,
                "{#HOST}": host,
                "{#HEALTH_PATH}": health,
                "{#PROMETHEUS_PATH}": prom,
                "{#TOKEN_FILE}": token,
            }
        )

    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
