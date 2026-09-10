#!/usr/bin/env python3

import json
import os

from scripts.log import get_logger

log = get_logger("config")


def _int_env(key: str, default: int) -> int:
  raw = os.getenv(key)
  if raw is None:
    return default
  try:
    return int(raw)
  except ValueError:
    log.warning(f"  ⚠ 非法环境变量 {key}={raw!r}，回退默认 {default}")
    return default


def _float_env(key: str, default: float) -> float:
  raw = os.getenv(key)
  if raw is None:
    return default
  try:
    return float(raw)
  except ValueError:
    log.warning(f"  ⚠ 非法环境变量 {key}={raw!r}，回退默认 {default}")
    return default


def _bool_env(key: str, default: bool) -> bool:
  raw = os.getenv(key)
  if raw is None:
    return default
  return raw.strip().lower() in ("1", "true", "yes", "on", "y")


SUBSCRIPTION_TIMEOUT = _int_env("PROXY_SUB_TIMEOUT", 30)
MAX_OUTPUT_NODES = _int_env("PROXY_MAX_OUTPUT_NODES", 200)
MINI_OUTPUT_NODES = _int_env("PROXY_MINI_OUTPUT_NODES", 100)

RELAY_ENABLED = _bool_env("PROXY_RELAY_ENABLED", True)
RELAY_CONCURRENCY = _int_env("PROXY_RELAY_CONCURRENCY", 50)
RELAY_MAX_RELAYS = _int_env("PROXY_RELAY_MAX_RELAYS", 5)
RELAY_MAX_PER_RELAY = _int_env("PROXY_RELAY_MAX_PER_RELAY", 0)
EXCLUDE_CN_OUTPUT = _bool_env("PROXY_EXCLUDE_CN_OUTPUT", True)
# 固定中国中继节点（如家里路由器）：Clash 风格节点 JSON 数组，注入 stage-2 relay 列表
RELAY_FIXED_ONLY = _bool_env("PROXY_RELAY_FIXED_ONLY", False)
RELAY_FIXED_NODES = []
_json_env = os.getenv("PROXY_RELAY_FIXED")
if _json_env:
  try:
    _parsed = json.loads(_json_env)
    if isinstance(_parsed, list):
      RELAY_FIXED_NODES = _parsed
    else:
      raise ValueError("not a list")
  except (ValueError, json.JSONDecodeError):
    log.warning("  ⚠ 非法 PROXY_RELAY_FIXED（应为 Clash 节点 JSON 数组），回退空列表")

MIHOMO_VERSION = os.getenv("PROXY_MIHOMO_VERSION", "v1.19.13")
TEST_URL = os.getenv("PROXY_TEST_URL", "https://www.gstatic.com/generate_204")
# CN relay stage-1 必须用国内可达的 204 端点（gstatic 被 GFW 拦，CN 出口物理不可达；
# baidu.com 返回 200+HTML 非 204，mihomo delay-test 视为失败，会误杀全部 CN relay 候选）
TEST_URL_CN = os.getenv("PROXY_TEST_URL_CN", "http://connect.rom.miui.com/generate_204")
# 必须明显大于 TEST_MAX_LATENCY：只留 500ms 余量时，节点稍一抖动就被判超时，
# 而它其实只是慢、并非不可用。代价是慢节点要多等一会儿才被判死。
TEST_TIMEOUT = _int_env("PROXY_TEST_TIMEOUT", 4000)
TEST_CONCURRENCY = _int_env("PROXY_TEST_CONCURRENCY", 100)
TEST_MAX_LATENCY = _int_env("PROXY_MAX_LATENCY", 1500)

PREFERRED_COUNTRIES = [
  c.strip().upper()
  for c in os.getenv("PROXY_PREFERRED_COUNTRIES", "US,KR,JP,SG,HK,TW").split(",")
  if c.strip()
]

# 带宽测速：延迟低 ≠ 可用，免费节点最常见的病灶是"能连上但带宽不足 1Mbps"。
# 只对 stage-2 存活的低延迟节点做，避免全量测速把 CI 拖爆。
SPEED_TEST = _bool_env("PROXY_SPEED_TEST", True)
SPEED_TOP_N = _int_env("PROXY_SPEED_TOP_N", 100)
SPEED_MIN_MBPS = _float_env("PROXY_SPEED_MIN_MBPS", 2.0)
SPEED_TIMEOUT = _int_env("PROXY_SPEED_TIMEOUT", 5)
SPEED_MAX_BYTES = _int_env("PROXY_SPEED_MAX_BYTES", 4 * 1024 * 1024)
SPEED_URL = os.getenv(
    "PROXY_SPEED_URL",
    "https://speed.cloudflare.com/__down?bytes=10000000",
)

GEOIP_DB_PATH = os.getenv("PROXY_GEOIP_DB", "geoip/GeoLite2-Country.mmdb")
GEOIP_DB_URL = os.getenv(
  "PROXY_GEOIP_DB_URL",
  "https://github.com/P3TERX/GeoLite.mmdb/releases/latest/download/GeoLite2-Country.mmdb",
)
GEOIP_MAX_AGE_DAYS = _int_env("PROXY_GEOIP_MAX_AGE_DAYS", 35)
GEOIP_DNS_WORKERS = _int_env("PROXY_GEOIP_DNS_WORKERS", 20)
