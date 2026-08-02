#!/usr/bin/env python3

import os


def _int_env(key: str, default: int) -> int:
  return int(os.getenv(key, str(default)))


def _bool_env(key: str, default: bool) -> bool:
  return os.getenv(key, str(int(default))).strip().lower() in ("1", "true", "yes", "on", "y")


SUBSCRIPTION_TIMEOUT = _int_env("PROXY_SUB_TIMEOUT", 10)
MAX_OUTPUT_NODES = _int_env("PROXY_MAX_OUTPUT_NODES", 200)
MINI_OUTPUT_NODES = _int_env("PROXY_MINI_OUTPUT_NODES", 100)

RELAY_ENABLED = _bool_env("PROXY_RELAY_ENABLED", True)
RELAY_CONCURRENCY = _int_env("PROXY_RELAY_CONCURRENCY", 50)
RELAY_MAX_RELAYS = _int_env("PROXY_RELAY_MAX_RELAYS", 5)
RELAY_MAX_PER_RELAY = _int_env("PROXY_RELAY_MAX_PER_RELAY", 0)
EXCLUDE_CN_OUTPUT = _bool_env("PROXY_EXCLUDE_CN_OUTPUT", True)

MIHOMO_VERSION = os.getenv("PROXY_MIHOMO_VERSION", "v1.19.13")
TEST_URL = os.getenv("PROXY_TEST_URL", "https://www.gstatic.com/generate_204")
# CN relay stage-1 必须用国内可达的 204 端点（gstatic 被 GFW 拦，CN 出口物理不可达；
# baidu.com 返回 200+HTML 非 204，mihomo delay-test 视为失败，会误杀全部 CN relay 候选）
TEST_URL_CN = os.getenv("PROXY_TEST_URL_CN", "http://connect.rom.miui.com/generate_204")
TEST_TIMEOUT = _int_env("PROXY_TEST_TIMEOUT", 2000)
TEST_CONCURRENCY = _int_env("PROXY_TEST_CONCURRENCY", 100)
TEST_MAX_LATENCY = _int_env("PROXY_MAX_LATENCY", 1500)

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
