#!/usr/bin/env python3
"""SS / SSR 协议 - SRP：本文件承载 SS/SSR 的全部协议知识。"""

import binascii
import urllib.parse
from typing import Dict, Optional

from scripts.log import get_logger
from scripts.protocols._helpers import (
  base_proxy,
  b64decode_str,
  b64encode,
  build_query,
  try_base64_decode,
  url_fragment,
)
from scripts.protocols.base import BaseProtocol

log = get_logger("ss")


class SSProtocol(BaseProtocol):
  """Shadowsocks（SIP008 + 旧格式）。"""

  @property
  def type_name(self) -> str:
    return "ss"

  def supports(self, uri: str) -> bool:
    return uri.startswith("ss://")

  def parse(self, url: str) -> Optional[Dict]:
    try:
      rest = url[5:]
      remark = ""
      if "#" in rest:
        rest, remark = rest.split("#", 1)
        remark = urllib.parse.unquote(remark)

      # Old format: ss://BASE64(method:password)@server:port
      if "@" in rest:
        b64_part, server_port = rest.split("@", 1)
        method_pass = try_base64_decode(b64_part) or b64_part
        if ":" not in method_pass or ":" not in server_port:
          return None
        method, password = method_pass.split(":", 1)
        server, port_str = server_port.rsplit(":", 1)
        port_str = port_str.split("?")[0]
      else:
        # SIP008: ss://BASE64(method:password@server:port)
        decoded = try_base64_decode(rest)
        if not decoded or "@" not in decoded:
          return None
        method_pass, server_port = decoded.split("@", 1)
        if ":" not in method_pass or ":" not in server_port:
          return None
        method, password = method_pass.split(":", 1)
        server, port_str = server_port.rsplit(":", 1)
        port_str = port_str.split("?")[0]

      return {
        "type": "ss",
        "name": remark[:50] or f"SS_{server[:15]}",
        "server": server,
        "port": int(port_str),
        "password": password,
        "cipher": method,
      }
    except (ValueError, IndexError, urllib.parse.InvalidURL) as e:
      log.warning(f"  ⚠ SS 解析失败: {url[:50]}... ({e})")
      return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
    base["cipher"] = node.get("cipher", "aes-256-gcm")
    base["password"] = node.get("password", "")
    return base

  def to_uri(self, node: Dict) -> Optional[str]:
    cipher = node.get("cipher", "aes-256-gcm")
    password = node.get("password", "")
    return f"ss://{b64encode(f'{cipher}:{password}')}@{node['server']}:{node['port']}#{url_fragment(node.get('name', ''))}"

  def dedup_key(self, node: Dict) -> str:
    return f"{super().dedup_key(node)}:{node.get('cipher', '')}:{node.get('password', '')}"

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("password") or not node.get("cipher"):
      return False
    return super().is_field_complete(node)


class SSRProtocol(BaseProtocol):
  """ShadowsocksR。"""

  @property
  def type_name(self) -> str:
    return "ssr"

  def supports(self, uri: str) -> bool:
    return uri.startswith("ssr://")

  def parse(self, url: str) -> Optional[Dict]:
    try:
      decoded = try_base64_decode(url[6:])
      if not decoded:
        return None
      parts = decoded.split(":")
      if len(parts) < 6:
        return None
      server = parts[0]
      port = int(parts[1])
      protocol = parts[2]
      cipher = parts[3]
      obfs = parts[4]
      password_b64 = parts[5]
      try:
        password = b64decode_str(password_b64)
      except (ValueError, binascii.Error):
        password = password_b64
      params = ""
      obfs_param = ""
      if "/?" in decoded:
        qs = urllib.parse.parse_qs(decoded.split("/?", 1)[1])
        params = qs.get("protoparam", [""])[0]
        obfs_param = qs.get("obfsparam", [""])[0]
      return {
        "type": "ssr",
        "name": f"SSR_{server[:15]}",
        "server": server,
        "port": port,
        "password": password,
        "cipher": cipher,
        "protocol": protocol,
        "obfs": obfs,
        "protocol-param": params,
        "obfs-param": obfs_param,
      }
    except (ValueError, IndexError, urllib.parse.InvalidURL) as e:
      log.warning(f"  ⚠ SSR 解析失败: {url[:50]}... ({e})")
      return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
    base["cipher"] = node.get("cipher", "aes-256-cfb")
    base["password"] = node.get("password", "")
    base["protocol"] = node.get("protocol", "origin")
    base["obfs"] = node.get("obfs", "plain")
    if node.get("protocol-param"):
      base["protocol-param"] = node["protocol-param"]
    if node.get("obfs-param"):
      base["obfs-param"] = node["obfs-param"]
    return base

  def to_uri(self, node: Dict) -> Optional[str]:
    main = (
      f"{node['server']}:{node['port']}:"
      f"{node.get('protocol', 'origin')}:{node.get('cipher', 'aes-256-cfb')}:"
      f"{node.get('obfs', 'plain')}:{b64encode(node.get('password', ''))}"
    )
    extra: Dict = {}
    if node.get("obfs-param"):
      extra["obfsparam"] = b64encode(node["obfs-param"])
    if node.get("protocol-param"):
      extra["protoparam"] = b64encode(node["protocol-param"])
    if node.get("name"):
      extra["remarks"] = b64encode(node["name"])
    if extra:
      main += "/?" + build_query(extra)
    return "ssr://" + b64encode(main)

  def dedup_key(self, node: Dict) -> str:
    return f"{super().dedup_key(node)}:{node.get('cipher', '')}:{node.get('password', '')}"

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("password") or not node.get("cipher"):
      return False
    return super().is_field_complete(node)
