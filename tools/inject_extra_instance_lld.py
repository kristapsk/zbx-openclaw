#!/usr/bin/env python3
"""Insert extra-instance LLD into Template_OpenClaw_Gateway_Agent2.yaml."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Template_OpenClaw_Gateway_Agent2.yaml"

TPL = "Template App OpenClaw Gateway"
PROM_MASTER = (
    'openclaw.prometheus["http://{#HOST}:{#PORT}{#PROMETHEUS_PATH}","{#TOKEN_FILE}"]'
)
HEALTH = 'openclaw.http.health["http://{#HOST}:{#PORT}{#HEALTH_PATH}"]'
LATENCY = 'openclaw.http.latency_ms["http://{#HOST}:{#PORT}{#HEALTH_PATH}"]'
LISTEN = "net.tcp.listen[{#PORT}]"


def uuid_for(name: str) -> str:
    """Deterministic Zabbix-style UUIDv4 (32 hex, version nibble 4)."""
    h = hashlib.md5(f"zbx-openclaw-lld:{name}".encode()).hexdigest()
    return f"{h[:12]}4{h[13:16]}8{h[17:32]}"


def suffix_key(key: str) -> str:
    if key.startswith("net.tcp.listen"):
        return LISTEN
    if key.startswith("openclaw.http.health"):
        return HEALTH
    if key.startswith("openclaw.http.latency_ms"):
        return LATENCY
    if key.startswith("openclaw.prometheus["):
        return PROM_MASTER
    if "[" in key:
        return key
    return f"{key}[{{#NAME}}]"


def rewrite_expr(expr: str, item_keys: list[str]) -> str:
    expr = expr.replace(
        'openclaw.prometheus["http://{$OPENCLAW_HOST}:{$OPENCLAW_PORT}{$OPENCLAW_PROMETHEUS_PATH}","{$OPENCLAW_PROMETHEUS_TOKEN_FILE}"]',
        PROM_MASTER,
    )
    expr = expr.replace(
        'openclaw.http.health["http://{$OPENCLAW_HOST}:{$OPENCLAW_PORT}{$OPENCLAW_HEALTH_PATH}"]',
        HEALTH,
    )
    expr = expr.replace(
        'openclaw.http.latency_ms["http://{$OPENCLAW_HOST}:{$OPENCLAW_PORT}{$OPENCLAW_HEALTH_PATH}"]',
        LATENCY,
    )
    expr = expr.replace("net.tcp.listen[{$OPENCLAW_PORT}]", LISTEN)
    # Longest first so metrics_present is not a prefix of a shorter token.
    for key in sorted(
        (k for k in item_keys if k.startswith("openclaw.") and "[" not in k),
        key=len,
        reverse=True,
    ):
        expr = expr.replace(
            f"/{TPL}/{key}",
            f"/{TPL}/{key}[{{#NAME}}]",
        )
    return expr


def proto_item(item: dict, item_keys: list[str]) -> tuple[dict, list[dict]]:
    out = dict(item)
    out["uuid"] = uuid_for(f"item:{item['key']}")
    out["name"] = item["name"].replace("OpenClaw:", "OpenClaw [{#NAME}]:", 1)
    out["key"] = suffix_key(item["key"])
    if item.get("type") == "DEPENDENT":
        out["master_item"] = {"key": PROM_MASTER}
    tags = list(item.get("tags") or [])
    tags.append({"tag": "instance", "value": "{#NAME}"})
    out["tags"] = tags
    lifted: list[dict] = []
    nested = out.pop("triggers", None)
    if nested:
        for trig in nested:
            lifted.append(proto_trigger(trig, item_keys, prefix="itemtrig"))
    return out, lifted


def proto_trigger(
    trig: dict, item_keys: list[str], prefix: str = "trig"
) -> dict:
    out = dict(trig)
    out["uuid"] = uuid_for(f"{prefix}:{trig['name']}")
    out["name"] = trig["name"].replace("OpenClaw:", "OpenClaw [{#NAME}]:", 1)
    out["expression"] = rewrite_expr(trig["expression"], item_keys)
    return out


def dump_yaml(obj, indent=0) -> str:
    """Minimal YAML dumper matching the template style."""
    import yaml

    return yaml.dump(
        obj,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )


def main() -> None:
    try:
        import yaml
    except ImportError:
        raise SystemExit("PyYAML required")

    doc = yaml.safe_load(TEMPLATE.read_text())
    export = doc.get("zabbix_export", doc)
    tmpl = export["templates"][0]
    items = tmpl["items"]
    triggers = export["triggers"]

    keys = [i["key"] for i in items]
    item_prototypes = []
    trigger_prototypes = []
    for it in items:
        proto, lifted = proto_item(it, keys)
        item_prototypes.append(proto)
        trigger_prototypes.extend(lifted)
    trigger_prototypes.extend(proto_trigger(tr, keys) for tr in triggers)

    discovery = {
        "uuid": uuid_for("discovery:extra-instances"),
        "name": "OpenClaw extra instances",
        "type": "ZABBIX_ACTIVE",
        "key": "openclaw.discovery[{$OPENCLAW_INSTANCES_FILE}]",
        "delay": "5m",
        "lifetime": "7d",
        "description": (
            "Additional OpenClaw Gateway instances on this host. "
            "The default instance stays on the static items/macros. "
            "A missing file yields an empty list and creates nothing."
        ),
        "item_prototypes": item_prototypes,
        "trigger_prototypes": trigger_prototypes,
    }
    tmpl["discovery_rules"] = [discovery]
    tmpl["description"] = (
        "Monitors a locally running OpenClaw Gateway with Zabbix agent2 active checks.\n"
        "\n"
        "Basic TCP and HTTP health monitoring works without the optional\n"
        "diagnostics-prometheus plugin. When that plugin is enabled, additional\n"
        "operational, usage, queue, memory and error metrics are collected from\n"
        "its authenticated Prometheus endpoint.\n"
        "\n"
        "A single Gateway needs only the host macros. Extra instances on the same\n"
        "host are discovered from {$OPENCLAW_INSTANCES_FILE} (empty/missing = none).\n"
    )
    macros = tmpl["macros"]
    if not any(m["macro"] == "{$OPENCLAW_INSTANCES_FILE}" for m in macros):
        macros.append(
            {
                "macro": "{$OPENCLAW_INSTANCES_FILE}",
                "value": "/etc/zabbix/openclaw.instances.json",
                "description": (
                    "JSON file of extra OpenClaw instances on this host. "
                    "Missing or empty means only the default instance is monitored."
                ),
            }
        )
        macros.sort(key=lambda m: m["macro"])

    # Keep export header comments-free; PyYAML dump of full doc may reorder
    # keys. Reconstruct from original file by splicing discovery_rules + macro.
    original = TEMPLATE.read_text()
    if "      discovery_rules:" in original:
        start = original.index("      discovery_rules:")
        end = original.index("      macros:")
        original = original[:start] + original[end:]
        original = original.replace(
            "        - macro: '{$OPENCLAW_INSTANCES_FILE}'\n"
            "          value: /etc/zabbix/openclaw.instances.json\n"
            "          description: 'JSON file of extra OpenClaw instances. Missing or empty = only the default instance.'\n",
            "",
            1,
        )
        extra = (
            "        A single Gateway needs only the host macros. Extra instances on the\n"
            "        same host are discovered from {$OPENCLAW_INSTANCES_FILE}. A missing or\n"
            "        empty file creates no extra items.\n"
        )
        original = original.replace(extra, "", 1)

    class IndentDumper(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    body = yaml.dump(
        tmpl["discovery_rules"],
        Dumper=IndentDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )
    disc_block = "      discovery_rules:\n" + "\n".join(
        ("        " + line) if line else "" for line in body.splitlines()
    )

    original = original.replace(
        "      macros:",
        disc_block + "\n      macros:",
        1,
    )
    original = original.replace(
        "        - macro: '{$OPENCLAW_HEALTH_PATH}'",
        "        - macro: '{$OPENCLAW_INSTANCES_FILE}'\n"
        "          value: /etc/zabbix/openclaw.instances.json\n"
        "          description: 'JSON file of extra OpenClaw instances. Missing or empty = only the default instance.'\n"
        "        - macro: '{$OPENCLAW_HEALTH_PATH}'",
        1,
    )
    # update description in place
    old_desc = (
        "        Monitors a locally running OpenClaw Gateway with Zabbix agent2 active checks.\n"
        "        \n"
        "        Basic TCP and HTTP health monitoring works without the optional\n"
        "        diagnostics-prometheus plugin. When that plugin is enabled, additional\n"
        "        operational, usage, queue, memory and error metrics are collected from\n"
        "        its authenticated Prometheus endpoint.\n"
    )
    new_desc = (
        "        Monitors a locally running OpenClaw Gateway with Zabbix agent2 active checks.\n"
        "        \n"
        "        Basic TCP and HTTP health monitoring works without the optional\n"
        "        diagnostics-prometheus plugin. When that plugin is enabled, additional\n"
        "        operational, usage, queue, memory and error metrics are collected from\n"
        "        its authenticated Prometheus endpoint.\n"
        "        \n"
        "        A single Gateway needs only the host macros. Extra instances on the\n"
        "        same host are discovered from {$OPENCLAW_INSTANCES_FILE}. A missing or\n"
        "        empty file creates no extra items.\n"
    )
    if old_desc not in original:
        raise SystemExit("template description block not found")
    original = original.replace(old_desc, new_desc, 1)
    TEMPLATE.write_text(original)
    print("updated", TEMPLATE)


if __name__ == "__main__":
    main()
