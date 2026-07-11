#!/usr/bin/env python3

import base64
import json
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from scripts.config import PREFERRED_COUNTRIES
from scripts.utils import extract_country, generate_node_name

OUTPUT_DIR = Path("output")
PROTOCOL_PRIORITY = {
  "hysteria2": 1, "trojan": 2, "tuic": 3, "vless-reality": 4, "vless": 5,
  "vmess": 6, "anytls": 7, "ss": 8, "ssr": 9,
  "socks5": 10, "http": 11,
}

_COUNTRY_RANK = {code: i for i, code in enumerate(PREFERRED_COUNTRIES)}


def _country_rank(node: Dict) -> int:
  code = extract_country(node.get("name", ""))
  return _COUNTRY_RANK.get(code, 99) if code else 99


def _protocol_rank(n: Dict) -> int:
  ptype = n.get("type", "").lower()
  if ptype == "vless" and n.get("reality-opts"):
    ptype = "vless-reality"
  return PROTOCOL_PRIORITY.get(ptype, 999)


def _sort_key(n: Dict) -> tuple:
  return (
    -n.get("_sub_priority", 0),
    _country_rank(n),
    _protocol_rank(n),
    n.get("latency", 9999),
  )


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


def _b64(s: str) -> str:
  return base64.b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")


def _frag(name: str) -> str:
  return urllib.parse.quote(name or "", safe="")


def _qval(v) -> str:
  return urllib.parse.quote(str(v), safe="")


def _query(params: Dict) -> str:
  return "&".join(f"{k}={_qval(v)}" for k, v in params.items() if v not in (None, ""))


def _to_uri(node: Dict) -> Optional[str]:
  ptype = node.get("type", "").lower()
  server = node.get("server", "")
  port = node.get("port", "")
  name = node.get("name", "")
  if not server or not port:
    return None
  try:
    if ptype == "ss":
      cipher = node.get("cipher", "aes-256-gcm")
      password = node.get("password", "")
      return f"ss://{_b64(f'{cipher}:{password}')}@{server}:{port}#{_frag(name)}"

    if ptype == "vmess":
      cfg = {
        "v": "2",
        "ps": name,
        "add": server,
        "port": str(port),
        "id": node.get("uuid", ""),
        "aid": str(node.get("alterId", 0)),
        "scy": node.get("security", "auto"),
        "net": node.get("network", "tcp"),
        "type": node.get("headerType", "none"),
        "host": node.get("host", ""),
        "path": node.get("path", ""),
        "tls": node.get("tls", ""),
        "sni": node.get("sni", ""),
        "alpn": node.get("alpn", ""),
      }
      return "vmess://" + _b64(json.dumps(cfg, ensure_ascii=False, indent=2))

    if ptype == "vless":
      params: Dict = {"encryption": "none"}
      reality = node.get("reality-opts") or {}
      if reality.get("public-key"):
        params["security"] = "reality"
        params["sni"] = node.get("sni", "")
        params["flow"] = node.get("flow", "")
        params["type"] = node.get("network", "tcp")
        params["host"] = node.get("host", "")
        params["path"] = node.get("path", "")
        params["pbk"] = reality.get("public-key", "")
        params["sid"] = reality.get("short-id", "")
        params["fp"] = node.get("client-fingerprint", "chrome")
      else:
        if node.get("security") == "tls" or node.get("tls"):
          params["security"] = "tls"
        params["sni"] = node.get("sni", "")
        params["flow"] = node.get("flow", "")
        net = node.get("network", "tcp")
        if net and net != "tcp":
          params["type"] = net
        params["host"] = node.get("host", "")
        params["path"] = node.get("path", "")
      q = _query(params)
      return f"vless://{node.get('uuid', '')}@{server}:{port}?{q}#{_frag(name)}"

    if ptype == "trojan":
      params: Dict = {}
      if node.get("sni"):
        params["security"] = "tls"
        params["sni"] = node["sni"]
      net = node.get("network", "tcp")
      if net and net != "tcp":
        params["type"] = net
      params["host"] = node.get("host", "")
      params["path"] = node.get("path", "")
      if node.get("skip-cert-verify"):
        params["allowInsecure"] = "1"
      q = _query(params)
      prefix = f"trojan://{node.get('password', '')}@{server}:{port}"
      return f"{prefix}?{q}#{_frag(name)}" if q else f"{prefix}#{_frag(name)}"

    if ptype == "hysteria2":
      params: Dict = {}
      if node.get("sni"):
        params["sni"] = node["sni"]
      if node.get("skip-cert-verify"):
        params["insecure"] = "1"
      q = _query(params)
      prefix = f"hysteria2://{node.get('password', '')}@{server}:{port}"
      return f"{prefix}?{q}#{_frag(name)}" if q else f"{prefix}#{_frag(name)}"

    if ptype == "ssr":
      password_b64 = _b64(node.get("password", ""))
      main = f"{server}:{port}:{node.get('protocol', 'origin')}:{node.get('cipher', 'aes-256-cfb')}:{node.get('obfs', 'plain')}:{password_b64}"
      extra: Dict = {}
      if node.get("obfs-param"):
        extra["obfsparam"] = _b64(node["obfs-param"])
      if node.get("protocol-param"):
        extra["protoparam"] = _b64(node["protocol-param"])
      if name:
        extra["remarks"] = _b64(name)
      if extra:
        main += "/?" + _query(extra)
      return "ssr://" + _b64(main)

  except Exception:
    return None
  return None


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

  # Plain URI lists (Hiddify-compatible) — full / mini / all
  def _write_uris(path: Path, nodes: List[Dict]):
    uris = [u for u in (_to_uri(n) for n in nodes) if u]
    with open(path, "w", encoding="utf-8") as f:
      f.write("\n".join(uris) + ("\n" if uris else ""))
    print(f"  \u2713 {path.name} ({len(uris)} \u8282\u70b9)")

  _write_uris(OUTPUT_DIR / "nodes.txt", selected)
  _write_uris(OUTPUT_DIR / "nodes_mini.txt", selected[:max_mini])

  # Debug JSON
  with open(OUTPUT_DIR / "valid_nodes.json", "w", encoding="utf-8") as f:
    json.dump(selected, f, indent=2, ensure_ascii=False)
  print(f"  \u2713 valid_nodes.json")

  # clash_all.yml: 全量可用节点（不截断）
  all_counters: Dict[str, int] = {}
  for node in valid_nodes:
    name = node.get("name", f"Node_{node['server']}")
    code = extract_country(name) or "XX"
    all_counters[code] = all_counters.get(code, 0) + 1
    node["name"] = generate_node_name(name, all_counters[code], node.get("latency", 9999))
  all_clash_nodes = [_to_clash_node(n) for n in valid_nodes]
  all_config = {
    "port": 7890,
    "socks-port": 7891,
    "allow-lan": True,
    "mode": "rule",
    "log-level": "warning",
    "proxies": all_clash_nodes,
    "proxy-groups": [
      {"name": "Proxy", "type": "select", "proxies": [n["name"] for n in all_clash_nodes]},
    ],
    "rules": ["MATCH,Proxy"],
  }
  all_path = OUTPUT_DIR / "clash_all.yml"
  with open(all_path, "w", encoding="utf-8") as f:
    f.write("---\n")
    yaml.dump(all_config, f, allow_unicode=True, sort_keys=False, indent=2)
  print(f"  \u2713 clash_all.yml ({len(all_clash_nodes)} \u8282\u70b9)")

  # nodes_all.txt: 全量可用节点 URI（不截断）
  _write_uris(OUTPUT_DIR / "nodes_all.txt", valid_nodes)

  # Stats
  type_counts: Dict[str, int] = {}
  for n in selected:
    t = n.get("type", "unknown")
    type_counts[t] = type_counts.get(t, 0) + 1
  for t, c in sorted(type_counts.items()):
    print(f"    {t.upper()}: {c}")
