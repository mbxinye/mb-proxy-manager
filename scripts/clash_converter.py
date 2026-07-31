#!/usr/bin/env python3
"""Clash 转换外观 - DIP：调用方依赖此模块而非具体协议实现；LKP：仅暴露 to_clash_node / to_uri。

协议具体逻辑由 protocols/ 注册表分派，本模块仅保留公共字段兜底
（未知协议类型回退最小 Clash proxy，由 mihomo -t 校验阶段剔除）。"""

from typing import Dict, Optional

from scripts.protocols._helpers import base_proxy
from scripts.protocols.registry import get_registry


def to_clash_node(node: Dict) -> Dict:
  """内部节点 -> Clash proxy 格式；未知类型回退最小 base（保持向后兼容）。"""
  clash = get_registry().to_clash(node)
  return clash if clash is not None else base_proxy(node)


def to_uri(node: Dict) -> Optional[str]:
  """内部节点 -> URI 字符串；无 URI 形态的协议返回 None。"""
  return get_registry().to_uri(node)
