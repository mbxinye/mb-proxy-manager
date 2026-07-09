#!/usr/bin/env python3

import os


def _int_env(key: str, default: int) -> int:
  return int(os.getenv(key, str(default)))


SUBSCRIPTION_TIMEOUT = _int_env("PROXY_SUB_TIMEOUT", 30)
MAX_OUTPUT_NODES = _int_env("PROXY_MAX_OUTPUT_NODES", 100)
MINI_OUTPUT_NODES = _int_env("PROXY_MINI_OUTPUT_NODES", 30)

MIHOMO_VERSION = os.getenv("PROXY_MIHOMO_VERSION", "v1.19.13")
MIHOMO_TEST_URL = os.getenv("PROXY_TEST_URL", "http://www.gstatic.com/generate_204")
MIHOMO_TEST_TIMEOUT = _int_env("PROXY_TEST_TIMEOUT", 2000)
PROXY_TEST_CONCURRENCY = _int_env("PROXY_TEST_CONCURRENCY", 100)
