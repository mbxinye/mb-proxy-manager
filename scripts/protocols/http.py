#!/usr/bin/env python3
"""HTTP / SOCKS5 协议 - 仅 Clash 转换 + 字段校验（无 URI 解析/序列化）。

ISP：这两个协议不需要解析与 URI 序列化，故仅实现 to_clash / is_field_complete，
其余接口沿用基类默认实现，避免强制依赖无关方法。"""

from typing import Dict, Optional

from scripts.protocols._helpers import base_proxy
from scripts.protocols.base import BaseProtocol


class _GenericAuthProtocol(BaseProtocol):
  """http/socks5 共用：用户名密码 + TLS，无 URI 形态。"""

  def to_clash(self, node: Dict) -> Optional[Dict]:
    base = base_proxy(node)
    if node.get("username"):
      base["username"] = node["username"]
    if node.get("password"):
      base["password"] = node["password"]
    if node.get("tls"):
      base["tls"] = True
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    return base

  def is_field_complete(self, node: Dict) -> bool:
    if not node.get("username") or not node.get("password"):
      return False
    return super().is_field_complete(node)


class HttpProtocol(_GenericAuthProtocol):
  @property
  def type_name(self) -> str:
    return "http"


class Socks5Protocol(_GenericAuthProtocol):
  @property
  def type_name(self) -> str:
    return "socks5"
