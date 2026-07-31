#!/usr/bin/env python3
"""VMess / VLESS 协议 - SRP：本文件承载 VMess/VLESS 的全部协议知识。"""

import json
import urllib.parse
from typing import Dict, Optional

from scripts.protocols._helpers import (
  apply_transport,
  base_proxy,
  b64encode,
  build_query,
  try_base64_decode,
  url_fragment,
)
from scripts.protocols.base import BaseProtocol


class VMessProtocol(BaseProtocol):
  """VMess。"""

  @property
  def type_name(self) -> str:
    return "vmess"

  def supports(self, uri: str) -> bool:
    return uri.startswith("vmess://")

  def parse(self, url: str) -> Optional[Dict]:
    try:
      decoded = try_base64_decode(url[8:])
      if not decoded:
        return None
      config = json.loads(decoded)
      node = {
        "type": "vmess",
        "name": config.get("ps", "VMess")[:50],
        "server": config.get("add", ""),
        "port": int(config.get("port", 443)),
        "uuid": config.get("id", ""),
        "alterId": int(config.get("aid", 0)),
        "security": config.get("scy", "auto"),
        "network": config.get("net", "tcp"),
        "tls": config.get("tls", ""),
      }
      for short, long in [("p", "path"), ("host", "host"), ("sni", "sni"), ("fp", "client-fingerprint"), ("alpn", "alpn")]:
        val = config.get(long) or config.get(short)
        if val:
          node[long] = val
      return node
    except Exception as e:
      print(f"  ⚠ VMess 解析失败: {url[:50]}... ({e})")
      return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
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
    apply_transport(base, node)
    return base

  def to_uri(self, node: Dict) -> Optional[str]:
    cfg = {
      "v": "2", "ps": node.get("name", ""), "add": node["server"], "port": str(node["port"]),
      "id": node.get("uuid", ""), "aid": str(node.get("alterId", 0)),
      "scy": node.get("security", "auto"), "net": node.get("network", "tcp"),
      "type": node.get("headerType", "none"), "host": node.get("host", ""),
      "path": node.get("path", ""), "tls": node.get("tls", ""),
      "sni": node.get("sni", ""), "alpn": node.get("alpn", ""),
    }
    return "vmess://" + b64encode(json.dumps(cfg, ensure_ascii=False, indent=2))

  def dedup_key(self, node: Dict) -> str:
    return f"{super().dedup_key(node)}:{node.get('uuid', '')}"

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("uuid"):
      return False
    return super().is_field_complete(node)


class VLESSProtocol(BaseProtocol):
  """VLESS（含 Reality）。"""

  @property
  def type_name(self) -> str:
    return "vless"

  def supports(self, uri: str) -> bool:
    return uri.startswith("vless://")

  def parse(self, url: str) -> Optional[Dict]:
    try:
      parsed = urllib.parse.urlparse(url)
      server = parsed.hostname
      if not server:
        return None
      uuid = parsed.username or ""
      query = urllib.parse.parse_qs(parsed.query)
      name = parsed.fragment or query.get("remarks", [f"VLESS_{server[:15]}"])[0]
      if name:
        name = urllib.parse.unquote(name)
      security = query.get("security", [""])[0]
      node: Dict = {
        "type": "vless",
        "name": name[:50],
        "server": server,
        "port": parsed.port or 443,
        "uuid": uuid,
      }
      if security == "xtls":
        node["flow"] = query.get("flow", [None])[0] or ""
      if query.get("sni", [None])[0]:
        node["sni"] = query["sni"][0]
      net = query.get("type", [None])[0] or query.get("network", [None])[0]
      if net:
        node["network"] = net
      if query.get("path", [None])[0]:
        node["path"] = query["path"][0]
      if query.get("host", [None])[0]:
        node["host"] = query["host"][0]
      if query.get("alpn", [None])[0]:
        node["alpn"] = query["alpn"][0]
      if security == "reality":
        reality_opts: Dict = {}
        pk = query.get("pbk", [None])[0]
        if pk:
          reality_opts["public-key"] = pk
        sid = query.get("sid", [None])[0]
        if sid:
          reality_opts["short-id"] = sid
        spx = query.get("spx", [""])[0]
        if spx:
          reality_opts["spider-x"] = spx
        if reality_opts:
          node["reality-opts"] = reality_opts
        node["client-fingerprint"] = query.get("fp", ["chrome"])[0]
      elif security == "tls":
        node["tls"] = True
      node["skip-cert-verify"] = query.get("allowInsecure", ["0"])[0] == "1"
      return node
    except Exception as e:
      print(f"  ⚠ VLESS 解析失败: {url[:50]}... ({e})")
      return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
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
    apply_transport(base, node)
    return base

  def to_uri(self, node: Dict) -> Optional[str]:
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
    if node.get("alpn"):
      params["alpn"] = node["alpn"]
    q = build_query(params)
    return f"vless://{node.get('uuid', '')}@{node['server']}:{node['port']}?{q}#{url_fragment(node.get('name', ''))}"

  def dedup_key(self, node: Dict) -> str:
    return f"{super().dedup_key(node)}:{node.get('uuid', '')}"

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("uuid"):
      return False
    # reality 必须有 public-key，否则 mihomo 加载 fatal
    reality = node.get("reality-opts") or {}
    if reality and not reality.get("public-key"):
      return False
    return super().is_field_complete(node)
