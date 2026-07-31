#!/usr/bin/env python3
"""去重模块 - SRP：只负责节点去重；OCP：去重键由协议注册表分派。"""

from typing import Dict, List, Set

from scripts.protocols.registry import get_registry


def _dedup_key(n: Dict) -> str:
  """生成去重键（含凭证，避免同地址不同凭证节点被误删）。"""
  return get_registry().dedup_key(n)


def dedup_nodes(nodes: List[Dict]) -> List[Dict]:
  """去重并保持顺序（首次出现保留）。"""
  seen: Set[str] = set()
  result: List[Dict] = []
  for n in nodes:
    key = _dedup_key(n)
    if key not in seen:
      seen.add(key)
      result.append(n)
  return result
