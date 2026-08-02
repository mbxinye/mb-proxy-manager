#!/usr/bin/env python3
"""统一日志配置 - SRP：仅负责日志器初始化；LKP：对外只暴露 get_logger。

替代散布各处的 print(...)：支持分级、可重定向、可在测试中静默。"""

import logging
import sys
import threading

_CONFIGURED = False
_config_lock = threading.Lock()


def _configure() -> None:
  global _CONFIGURED
  if _CONFIGURED:
    return
  with _config_lock:
    if _CONFIGURED:
      return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("mbproxy")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str = "mbproxy") -> logging.Logger:
  """获取统一命名空间下的 logger。"""
  _configure()
  return logging.getLogger(f"mbproxy.{name}")


def set_level(level: int) -> None:
  """测试钩子：调整日志级别（如 logging.CRITICAL 可静默）。"""
  _configure()
  logging.getLogger("mbproxy").setLevel(level)
