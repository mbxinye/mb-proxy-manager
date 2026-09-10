#!/usr/bin/env python3
"""通用网络辅助 - SRP：只放跨模块复用的纯工具函数。"""

from urllib.request import ProxyHandler, build_opener


def get_local_opener():
  """获取绕过系统代理的 opener，避免 127.0.0.1 被系统代理劫持。"""
  return build_opener(ProxyHandler({}))


def effective_latency(node: dict) -> int:
  """排序/展示统一使用的延迟：优先国内出口视角（stage-2 经中继测得）。

  latency 是 runner（美国出口）直连值，对国内用户无参考意义；
  relay_latency 才是"国内出口→节点"的延迟。有后者就必须用后者。"""
  v = node.get("relay_latency")
  if v:
    return int(v)
  return int(node.get("latency", 9999) or 9999)
