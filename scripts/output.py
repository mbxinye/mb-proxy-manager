#!/usr/bin/env python3

import json
from pathlib import Path
from typing import Dict, List

import yaml

from scripts.utils import extract_country, generate_node_name

OUTPUT_DIR = Path("output")
PROTOCOL_PRIORITY = {
  "vless": 1, "vmess": 2, "trojan": 3, "hysteria2": 4,
  "tuic": 5, "anytls": 6, "ss": 7, "ssr": 8, "socks5": 9, "http": 10,
}


def _sort_key(n: Dict) -> tuple:
  return (n.get("latency", 9999), PROTOCOL_PRIORITY.get(n.get("type", "").lower(), 999))


def _to_clash_node(node: Dict) -> Dict:
  ptype = node.get("type", "").lower()
  base = {
    "name": node["name"],
    "type": ptype,
    "server": node["server"],
    "port": str(int(node["port"])),
  }

  if node.get("udp"):
    base["udp"] = True

  if ptype == "ss":
    base["cipher"] = node.get("cipher", "aes-256-gcm")
    base["password"] = node.get("password", "")

  elif ptype == "ssr":
    base["cipher"] = node.get("cipher", "aes-256-cfb")
    base["password"] = node.get("password", "")
    base["protocol"] = node.get("protocol", "origin")
    base["obfs"] = node.get("obfs", "plain")
    if node.get("protocol-param"):
      base["protocol-param"] = node["protocol-param"]
    if node.get("obfs-param"):
      base["obfs-param"] = node["obfs-param"]

  elif ptype == "vmess":
    base["uuid"] = node.get("uuid", "")
    base["alterId"] = int(node.get("alterId", 0))
    base["cipher"] = node.get("security", "auto")
    if node.get("tls"):
      base["tls"] = True
      sni = node.get("sni") or node.get("servername")
      if sni:
        base["servername"] = sni
    if "skip-cert-verify" in node:
      base["skip-cert-verify"] = node["skip-cert-verify"]
    network = node.get("network", "tcp")
    if network in ("ws", "websocket"):
      base["network"] = "ws"
      if node.get("ws-opts"):
        base["ws-opts"] = node["ws-opts"]
      else:
        ws_opts = {}
        if node.get("path"):
          ws_opts["path"] = node["path"]
        if node.get("host"):
          ws_opts["headers"] = {"Host": node["host"]}
        if ws_opts:
          base["ws-opts"] = ws_opts

  elif ptype == "trojan":
    base["password"] = node.get("password", "")
    if node.get("sni"):
      base["sni"] = node["sni"]
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    network = node.get("network", "")
    if network in ("ws", "websocket"):
      base["network"] = "ws"
      if node.get("ws-opts"):
        base["ws-opts"] = node["ws-opts"]
      else:
        ws_opts = {}
        if node.get("path"):
          ws_opts["path"] = node["path"]
        if node.get("host"):
          ws_opts["headers"] = {"Host": node["host"]}
        if ws_opts:
          base["ws-opts"] = ws_opts

  elif ptype == "vless":
    base["uuid"] = node.get("uuid", "")
    if node.get("flow"):
      base["flow"] = node["flow"]
    sni = node.get("sni") or node.get("servername")
    if sni:
      base["servername"] = sni
    reality = node.get("reality-opts") or {}
    if reality.get("public-key"):
      base["tls"] = True
      base["reality-opts"] = reality
      base["client-fingerprint"] = node.get("client-fingerprint", "chrome")
    elif node.get("tls"):
      base["tls"] = True
    if "skip-cert-verify" in node:
      base["skip-cert-verify"] = node["skip-cert-verify"]
    network = node.get("network", "tcp")
    if network in ("ws", "websocket"):
      base["network"] = "ws"
      if node.get("ws-opts"):
        base["ws-opts"] = node["ws-opts"]
      else:
        ws_opts = {}
        if node.get("path"):
          ws_opts["path"] = node["path"]
        if node.get("host"):
          ws_opts["headers"] = {"Host": node["host"]}
        if ws_opts:
          base["ws-opts"] = ws_opts

  elif ptype == "hysteria2":
    base["password"] = node.get("password", "")
    if node.get("sni"):
      base["sni"] = node["sni"]
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    if node.get("up"):
      base["up"] = node["up"]
    if node.get("down"):
      base["down"] = node["down"]

  elif ptype in ("http", "socks5"):
    if node.get("username"):
      base["username"] = node["username"]
    if node.get("password"):
      base["password"] = node["password"]
    if node.get("tls"):
      base["tls"] = True
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True

  return base


def write(valid_nodes: List[Dict], max_full: int, max_mini: int):
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  valid_nodes.sort(key=_sort_key)
  selected = valid_nodes[:max_full]

  # Generate display names
  counters: Dict[str, int] = {}
  for node in selected:
    name = node.get("name", f"Node_{node['server']}")
    code = extract_country(name) or "XX"
    counters[code] = counters.get(code, 0) + 1
    node["name"] = generate_node_name(name, counters[code], node.get("latency", 9999))

  clash_nodes = [_to_clash_node(n) for n in selected]

  # Full config
  full_config = {
    "port": 7890,
    "socks-port": 7891,
    "allow-lan": True,
    "mode": "rule",
    "log-level": "warning",
    "proxies": clash_nodes,
    "proxy-groups": [
      {
        "name": "Proxy",
        "type": "select",
        "proxies": [n["name"] for n in clash_nodes],
      },
    ],
    "rules": ["MATCH,Proxy"],
  }

  full_path = OUTPUT_DIR / "clash_config.yml"
  with open(full_path, "w", encoding="utf-8") as f:
    f.write("---\n")
    yaml.dump(full_config, f, allow_unicode=True, sort_keys=False, indent=2)
  print(f"  \u2713 clash_config.yml ({len(clash_nodes)} \u8282\u70b9)")

  # Mini config
  mini_nodes = clash_nodes[:max_mini]
  mini_config = dict(full_config)
  mini_config["proxies"] = mini_nodes
  mini_config["proxy-groups"] = [
    {
      "name": "Proxy",
      "type": "select",
      "proxies": [n["name"] for n in mini_nodes],
    },
  ]
  mini_path = OUTPUT_DIR / "clash_mini.yml"
  with open(mini_path, "w", encoding="utf-8") as f:
    f.write("---\n")
    yaml.dump(mini_config, f, allow_unicode=True, sort_keys=False, indent=2)
  print(f"  \u2713 clash_mini.yml ({len(mini_nodes)} \u8282\u70b9)")

  # Debug JSON
  with open(OUTPUT_DIR / "valid_nodes.json", "w", encoding="utf-8") as f:
    json.dump(selected, f, indent=2, ensure_ascii=False)
  print(f"  \u2713 valid_nodes.json")

  # Stats
  type_counts: Dict[str, int] = {}
  for n in selected:
    t = n.get("type", "unknown")
    type_counts[t] = type_counts.get(t, 0) + 1
  for t, c in sorted(type_counts.items()):
    print(f"    {t.upper()}: {c}")
