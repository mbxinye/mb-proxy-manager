#!/usr/bin/env python3
"""Trojan / Hysteria2 协议 - SRP：本文件承载 Trojan/Hysteria2 的全部协议知识。"""

import urllib.parse
from typing import Dict, Optional

from scripts.log import get_logger
from scripts.protocols._helpers import (
  apply_transport,
  base_proxy,
  build_query,
  get_sni,
  normalize_alpn,
  url_fragment,
)
from scripts.protocols.base import BaseProtocol

log = get_logger("trojan")


class TrojanProtocol(BaseProtocol):
  """Trojan。"""

  @property
  def type_name(self) -> str:
    return "trojan"

  def supports(self, uri: str) -> bool:
    return uri.startswith("trojan://")

  def parse(self, url: str) -> Optional[Dict]:
    try:
      parsed = urllib.parse.urlparse(url)
      server = parsed.hostname
      if not server:
        return None
      query = urllib.parse.parse_qs(parsed.query)
      name = parsed.fragment or query.get("remarks", [f"Trojan_{server[:15]}"])[0]
      if name:
        name = urllib.parse.unquote(name)
      node: Dict = {
        "type": "trojan",
        "name": name[:50],
        "server": server,
        "port": parsed.port or 443,
        "password": parsed.username or "",
      }
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
      node["skip-cert-verify"] = query.get("allowInsecure", ["0"])[0] == "1"
      return node
    except (ValueError, KeyError, urllib.parse.InvalidURL) as e:
      log.warning(f"  ⚠ Trojan 解析失败: {url[:50]}... ({e})")
      return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
    base["password"] = node.get("password", "")
    if node.get("sni"):
      base["sni"] = node["sni"]
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    apply_transport(base, node)
    return base

  def to_uri(self, node: Dict) -> Optional[str]:
    params: Dict = {}
    if node.get("sni"):
      params["security"] = "tls"
      params["sni"] = node["sni"]
    net = node.get("network", "tcp")
    if net and net != "tcp":
      params["type"] = net
    params["host"] = node.get("host", "")
    params["path"] = node.get("path", "")
    if node.get("alpn"):
      params["alpn"] = node["alpn"]
    if node.get("skip-cert-verify"):
      params["allowInsecure"] = "1"
    q = build_query(params)
    prefix = f"trojan://{node.get('password', '')}@{node['server']}:{node['port']}"
    return f"{prefix}?{q}#{url_fragment(node.get('name', ''))}" if q else f"{prefix}#{url_fragment(node.get('name', ''))}"

  def dedup_key(self, node: Dict) -> str:
    return f"{super().dedup_key(node)}:{node.get('password', '')}"

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("password"):
      return False
    return super().is_field_complete(node)


class Hysteria2Protocol(BaseProtocol):
  """Hysteria2。"""

  @property
  def type_name(self) -> str:
    return "hysteria2"

  def supports(self, uri: str) -> bool:
    return uri.startswith("hysteria2://") or uri.startswith("hy2://")

  def parse(self, url: str) -> Optional[Dict]:
    try:
      parsed = urllib.parse.urlparse(url)
      server = parsed.hostname
      if not server:
        return None
      query = urllib.parse.parse_qs(parsed.query)
      name = parsed.fragment or query.get("remarks", [f"Hysteria2_{server[:15]}"])[0]
      if name:
        name = urllib.parse.unquote(name)
      node: Dict = {
        "type": "hysteria2",
        "name": name[:50],
        "server": server,
        "port": parsed.port or 443,
        "password": parsed.username or "",
      }
      if query.get("sni", [None])[0]:
        node["sni"] = query["sni"][0]
      if query.get("insecure", ["0"])[0] == "1":
        node["skip-cert-verify"] = True
      obfs = query.get("obfs", [None])[0]
      if obfs:
        node["obfs"] = obfs
        obfs_pwd = query.get("obfs-password", [None])[0]
        if obfs_pwd:
          node["obfs-password"] = obfs_pwd
      up = query.get("up", [None])[0]
      if up:
        node["up"] = up
      down = query.get("down", [None])[0]
      if down:
        node["down"] = down
      alpn = query.get("alpn", [None])[0]
      if alpn:
        node["alpn"] = alpn
      return node
    except (ValueError, KeyError, urllib.parse.InvalidURL) as e:
      log.warning(f"  ⚠ Hysteria2 解析失败: {url[:50]}... ({e})")
      return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
    base["password"] = node.get("password", "")
    if node.get("sni"):
      base["sni"] = node["sni"]
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    if node.get("obfs"):
      base["obfs"] = node["obfs"]
    if node.get("obfs-password"):
      base["obfs-password"] = node["obfs-password"]
    if node.get("up"):
      base["up"] = node["up"]
    if node.get("down"):
      base["down"] = node["down"]
    alpn = normalize_alpn(node.get("alpn"))
    if alpn:
      base["alpn"] = alpn
    return base

  def to_uri(self, node: Dict) -> Optional[str]:
    params: Dict = {}
    if node.get("sni"):
      params["sni"] = node["sni"]
    if node.get("obfs"):
      params["obfs"] = node["obfs"]
    if node.get("obfs-password"):
      params["obfs-password"] = node["obfs-password"]
    if node.get("insecure") or node.get("skip-cert-verify"):
      params["insecure"] = "1"
    if node.get("up"):
      params["up"] = node["up"]
    if node.get("down"):
      params["down"] = node["down"]
    if node.get("alpn"):
      params["alpn"] = node["alpn"]
    q = build_query(params)
    prefix = f"hysteria2://{node.get('password', '')}@{node['server']}:{node['port']}"
    return f"{prefix}?{q}#{url_fragment(node.get('name', ''))}" if q else f"{prefix}#{url_fragment(node.get('name', ''))}"

  def dedup_key(self, node: Dict) -> str:
    return f"{super().dedup_key(node)}:{node.get('password', '')}"

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("password"):
      return False
    return super().is_field_complete(node)
