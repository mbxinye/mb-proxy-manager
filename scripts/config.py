#!/usr/bin/env python3

import os


def _int_env(key: str, default: int) -> int:
  return int(os.getenv(key, str(default)))


SUBSCRIPTION_TIMEOUT = _int_env("PROXY_SUB_TIMEOUT", 30)
TCP_TIMEOUT = _int_env("PROXY_TCP_TIMEOUT", 3)
BATCH_SIZE = _int_env("PROXY_BATCH_SIZE", 200)
MAX_LATENCY = _int_env("PROXY_MAX_LATENCY", 5000)
MAX_OUTPUT_NODES = _int_env("PROXY_MAX_OUTPUT_NODES", 100)
MINI_OUTPUT_NODES = _int_env("PROXY_MINI_OUTPUT_NODES", 30)
