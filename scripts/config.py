#!/usr/bin/env python3

import os


def _int_env(key: str, default: int) -> int:
  return int(os.getenv(key, str(default)))


def _bool_env(key: str, default: bool) -> bool:
  return os.getenv(key, str(int(default))).strip().lower() in ("1", "true", "yes", "on", "y")


SUBSCRIPTION_TIMEOUT = _int_env("PROXY_SUB_TIMEOUT", 30)
MAX_OUTPUT_NODES = _int_env("PROXY_MAX_OUTPUT_NODES", 200)
MINI_OUTPUT_NODES = _int_env("PROXY_MINI_OUTPUT_NODES", 100)

RELAY_ENABLED = _bool_env("PROXY_RELAY_ENABLED", True)
RELAY_CONCURRENCY = _int_env("PROXY_RELAY_CONCURRENCY", 50)
RELAY_MAX_RELAYS = _int_env("PROXY_RELAY_MAX_RELAYS", 5)
RELAY_MAX_PER_RELAY = _int_env("PROXY_RELAY_MAX_PER_RELAY", 0)
EXCLUDE_CN_OUTPUT = _bool_env("PROXY_EXCLUDE_CN_OUTPUT", True)

# External China-relay sources (e.g. free-proxy aggregators). When the
# subscription pool has few mainland-CN nodes, these are fetched, given a
# stage-1 reachability test from the runner, and then tried in stage-2 AFTER
# the subscription CN relays. They never appear in the final output.
RELAY_EXTERNAL_ENABLED = _bool_env("PROXY_RELAY_EXTERNAL_ENABLED", True)
RELAY_EXTERNAL_SOURCES = [
  s.strip() for s in os.getenv("PROXY_RELAY_EXTERNAL_SOURCES", "freevpnnode,proxyscrape").split(",")
  if s.strip()
]
RELAY_EXTERNAL_PAGES = _int_env("PROXY_RELAY_EXTERNAL_PAGES", 3)
RELAY_EXTERNAL_PROTOCOLS = [
  p.strip().lower() for p in os.getenv("PROXY_RELAY_EXTERNAL_PROTOCOLS", "socks5,http").split(",")
  if p.strip()
]
RELAY_EXTERNAL_MAX = _int_env("PROXY_RELAY_EXTERNAL_MAX", 5)
RELAY_EXTERNAL_LATENCY = _int_env("PROXY_RELAY_EXTERNAL_LATENCY", 2500)

MIHOMO_VERSION = os.getenv("PROXY_MIHOMO_VERSION", "v1.19.13")
MIHOMO_TEST_URL = os.getenv("PROXY_TEST_URL", "https://www.gstatic.com/generate_204")
# CN relay stage-1 必须用国内可达目标（gstatic 被 GFW 拦，CN 出口物理不可达）
MIHOMO_TEST_URL_CN = os.getenv("PROXY_TEST_URL_CN", "https://www.baidu.com/")
MIHOMO_TEST_TIMEOUT = _int_env("PROXY_TEST_TIMEOUT", 2000)
PROXY_TEST_CONCURRENCY = _int_env("PROXY_TEST_CONCURRENCY", 100)
MAX_LATENCY = _int_env("PROXY_MAX_LATENCY", 1500)

PREFERRED_COUNTRIES = [
  c.strip().upper()
  for c in os.getenv("PROXY_PREFERRED_COUNTRIES", "US,KR,JP,SG,HK,TW").split(",")
  if c.strip()
]

GEOIP_DB_PATH = os.getenv("PROXY_GEOIP_DB", "geoip/GeoLite2-Country.mmdb")
GEOIP_DB_URL = os.getenv(
  "PROXY_GEOIP_DB_URL",
  "https://github.com/P3TERX/GeoLite.mmdb/releases/latest/download/GeoLite2-Country.mmdb",
)
GEOIP_MAX_AGE_DAYS = _int_env("PROXY_GEOIP_MAX_AGE_DAYS", 35)
GEOIP_DNS_WORKERS = _int_env("PROXY_GEOIP_DNS_WORKERS", 20)
