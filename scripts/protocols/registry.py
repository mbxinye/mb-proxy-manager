#!/usr/bin/env python3
"""协议注册表 - OCP：新增协议只需新增子类并在 _build() 中注册，无需改动调用方。

LKP：调用方仅依赖 get_registry() 与分派方法，不感知具体协议类。
DIP：调用方依赖此抽象注册表而非具体协议实现。"""

from typing import Dict, List, Optional

from scripts.protocols.base import BaseProtocol


class ProtocolRegistry:
  """按 node.type 分派到对应协议实例；URI 解析按注册顺序匹配。"""

  def __init__(self):
    self._by_type: Dict[str, BaseProtocol] = {}

  def register(self, protocol: BaseProtocol) -> None:
    self._by_type[protocol.type_name.lower()] = protocol

  def get(self, type_name: str) -> Optional[BaseProtocol]:
    return self._by_type.get((type_name or "").lower())

  def parse(self, uri: str) -> Optional[Dict]:
    for protocol in self._by_type.values():
      if protocol.supports(uri):
        return protocol.parse(uri)
    return None

  def to_clash(self, node: Dict) -> Optional[Dict]:
    protocol = self.get(node.get("type", ""))
    return protocol.to_clash(node) if protocol else None

  def to_uri(self, node: Dict) -> Optional[str]:
    protocol = self.get(node.get("type", ""))
    return protocol.to_uri(node) if protocol else None

  def dedup_key(self, node: Dict) -> str:
    protocol = self.get(node.get("type", ""))
    if protocol:
      return protocol.dedup_key(node)
    t = node.get("type", "")
    return f"{node.get('server', '')}:{node.get('port', '')}:{t}"

  def is_field_complete(self, node: Dict) -> bool:
    protocol = self.get(node.get("type", ""))
    return protocol.is_field_complete(node) if protocol else True

  @property
  def protocols(self) -> List[BaseProtocol]:
    return list(self._by_type.values())


_registry: Optional[ProtocolRegistry] = None


def get_registry() -> ProtocolRegistry:
  global _registry
  if _registry is None:
    _registry = ProtocolRegistry()
    from scripts.protocols.http import HttpProtocol, Socks5Protocol
    from scripts.protocols.ss import SSProtocol, SSRProtocol
    from scripts.protocols.trojan import Hysteria2Protocol, TrojanProtocol
    from scripts.protocols.vmess import VLESSProtocol, VMessProtocol

    # 解析型协议（顺序决定 URI 分派优先级，先注册先匹配）
    _registry.register(SSProtocol())
    _registry.register(SSRProtocol())
    _registry.register(VMessProtocol())
    _registry.register(VLESSProtocol())
    _registry.register(TrojanProtocol())
    _registry.register(Hysteria2Protocol())
    # 纯转换型协议（仅 Clash 配置中可能出现）
    _registry.register(HttpProtocol())
    _registry.register(Socks5Protocol())
  return _registry


def reset_registry() -> None:
  """测试钩子：重置全局注册表，便于注入 mock 或重新初始化。"""
  global _registry
  _registry = None


def set_registry(registry: ProtocolRegistry) -> None:
  """测试钩子：注入自定义注册表实例（依赖倒置，便于测试替换）。"""
  global _registry
  _registry = registry
