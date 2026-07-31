#!/usr/bin/env python3
"""
去重模块 - SRP: 只负责节点去重；OCP: 协议类型可扩展

从 main.py 中提取，保持纯函数设计。
"""

from typing import Dict, List, Set


def _dedup_key(n: Dict) -> str:
  """生成去重键（含凭证，避免同地址不同凭证节点被误删）"""
  t = n.get("type", "")
  base = f"{n.get('server', '')}:{n.get('port', '')}:{t}"
  if t in ("ss", "ssr"):
    return f"{base}:{n.get('cipher', '')}:{n.get('password', '')}"
  if t in ("vmess", "vless"):
    return f"{base}:{n.get('uuid', '')}"
  if t in ("trojan", "hysteria2"):
    return f"{base}:{n.get('password', '')}"
  return base


def dedup_nodes(nodes: List[Dict]) -> List[Dict]:
  """去重并保持顺序（首次出现保留）"""
  seen: Set[str] = set()
  result: List[Dict] = []
  for n in nodes:
    key = _dedup_key(n)
    if key not in seen:
      seen.add(key)
      result.append(n)
  return result