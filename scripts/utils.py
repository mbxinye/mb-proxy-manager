#!/usr/bin/env python3
"""通用网络辅助 - SRP：只放跨模块复用的纯工具函数。"""

from urllib.request import ProxyHandler, build_opener


def get_local_opener():
  """获取绕过系统代理的 opener，避免 127.0.0.1 被系统代理劫持。"""
  return build_opener(ProxyHandler({}))
