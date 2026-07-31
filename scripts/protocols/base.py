#!/usr/bin/env python3
"""协议基类 - OCP：新增协议只需新增子类并注册；SRP：每协议自管全部行为。

接口隔离（ISP）：parse / to_uri 等仅部分协议需要的接口给出默认实现，
不强制纯转换型协议（如 http/socks5）实现解析。"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseProtocol(ABC):
  """协议统一抽象：解析 + Clash 转换 + URI 序列化 + 去重键 + 字段校验。"""

  @property
  @abstractmethod
  def type_name(self) -> str:
    """节点 type 字段值，如 'ss' / 'vmess'，用于注册表按类型分派。"""

  def supports(self, uri: str) -> bool:
    """是否支持该 URI（仅解析阶段使用）；纯转换型协议默认 False。"""
    return False

  def parse(self, uri: str) -> Optional[Dict]:
    """URI -> 内部节点 dict；无 URI 格式的协议返回 None。"""
    return None

  @abstractmethod
  def to_clash(self, node: Dict) -> Optional[Dict]:
    """内部节点 -> Clash proxy dict（注册协议必须可转 Clash）。"""

  def to_uri(self, node: Dict) -> Optional[str]:
    """内部节点 -> URI 字符串；无 URI 格式的协议返回 None。"""
    return None

  def dedup_key(self, node: Dict) -> str:
    """去重键（含地址与类型，避免误删同地址不同协议节点）。"""
    t = node.get("type", "")
    return f"{node.get('server', '')}:{node.get('port', '')}:{t}"

  def is_field_complete(self, node: Dict) -> bool:
    """跨协议通用校验：WS 传输必须有 path；其余由子类叠加协议凭证校验。

    注意：TLS 节点缺 sni/servername 时不剔除——mihomo 会回退用 server 字段作 SNI，
    强校验会误杀大量合法节点。"""
    if node.get("network") in ("ws", "websocket"):
      ws_opts = node.get("ws-opts") or {}
      if "path" not in ws_opts and not node.get("path"):
        return False
    return True
