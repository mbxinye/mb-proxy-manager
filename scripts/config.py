#!/usr/bin/env python3

import os


def _int_env(key: str, default: int) -> int:
  return int(os.getenv(key, str(default)))


SUBSCRIPTION_TIMEOUT = _int_env("PROXY_SUB_TIMEOUT", 30)
MAX_OUTPUT_NODES = _int_env("PROXY_MAX_OUTPUT_NODES", 200)
MINI_OUTPUT_NODES = _int_env("PROXY_MINI_OUTPUT_NODES", 100)

MIHOMO_VERSION = os.getenv("PROXY_MIHOMO_VERSION", "v1.19.13")
MIHOMO_TEST_URL = os.getenv("PROXY_TEST_URL", "https://www.gstatic.com/generate_204")
MIHOMO_TEST_TIMEOUT = _int_env("PROXY_TEST_TIMEOUT", 2000)
PROXY_TEST_CONCURRENCY = _int_env("PROXY_TEST_CONCURRENCY", 100)
MAX_LATENCY = _int_env("PROXY_MAX_LATENCY", 1500)

PREFERRED_COUNTRIES = [
  c.strip().upper()
  for c in os.getenv("PROXY_PREFERRED_COUNTRIES", "US,KR,JP,SG,HK,TW").split(",")
  if c.strip()
]
