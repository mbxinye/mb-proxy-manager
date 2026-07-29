#!/usr/bin/env python3

from typing import Dict, List

from scripts import mihomo
from scripts.config import (
  EXCLUDE_CN_OUTPUT,
  MIHOMO_TEST_URL_CN,
  RELAY_ENABLED,
  RELAY_MAX_PER_RELAY,
  RELAY_MAX_RELAYS,
)
from scripts.geoip import prefetch_countries
from scripts.utils import is_china_node


def _is_field_complete(node: Dict) -> bool:
  ptype = node.get("type", "").lower()

  # 各协议必填凭证（mihomo 启动时严格校验，缺失会 fatal 中断整个配置加载）
  if ptype == "ss":
    if not node.get("password") or not node.get("cipher"):
      return False
  elif ptype == "ssr":
    if not node.get("password") or not node.get("cipher"):
      return False
  elif ptype == "trojan":
    if not node.get("password"):
      return False
  elif ptype == "hysteria2":
    if not node.get("password"):
      return False
  elif ptype == "vmess":
    if not node.get("uuid"):
      return False
  elif ptype == "vless":
    if not node.get("uuid"):
      return False
  elif ptype in ("http", "socks5"):
    if not node.get("username") or not node.get("password"):
      return False

  # WS 传输必须有 path
  if node.get("network") in ("ws", "websocket"):
    ws_opts = node.get("ws-opts") or {}
    if "path" not in ws_opts and not node.get("path"):
      return False

  # TLS 节点必须有 sni/servername（mihomo 要求）
  if node.get("tls"):
    if not node.get("servername") and not node.get("sni"):
      return False

  return True


def run(nodes: List[Dict]) -> List[Dict]:
  total = len(nodes)

  complete = [n for n in nodes if _is_field_complete(n)]
  dropped = total - len(complete)
  if dropped:
    print(f"  \u5b57\u6bb5\u4e0d\u5b8c\u6574\u629b\u5f03: {dropped}/{total}")

  # Stage-1 前先分流 CN/foreign：CN 出口物理上无法访问 GFW 外目标（gstatic），
  # 必须用国内可达 URL 测可达性，否则 CN relay 候选会在 stage-1 全部被误杀。
  prefetch_countries([n.get("server", "") for n in complete])
  china_candidates: List[Dict] = []
  foreign_candidates: List[Dict] = []
  for n in complete:
    if is_china_node(
      n.get("name", ""),
      n.get("server", ""),
      n.get("sni", "") or n.get("servername", "") or "",
    ):
      china_candidates.append(n)
    else:
      foreign_candidates.append(n)
  print(f"  \u5206\u6d41: CN relay {len(china_candidates)} / foreign {len(foreign_candidates)}")

  # CN relay 用国内 URL（baidu），foreign 用 gstatic
  cn_valid = mihomo.test_nodes(china_candidates, test_url=MIHOMO_TEST_URL_CN) if china_candidates else []
  foreign_valid = mihomo.test_nodes(foreign_candidates) if foreign_candidates else []
  valid = cn_valid + foreign_valid

  china = cn_valid
  china_ids = {id(n) for n in china}
  foreign = foreign_valid
  print(f"  stage-1: {len(valid)} reachable (CN relay {len(china)} / foreign {len(foreign)})")

  # Stage-2: re-test foreign nodes through China relays (dialer-proxy).
  # This verifies reachability from a China network egress, the view that
  # actually matters for the user. Failure here == the unusable nodes.
  if RELAY_ENABLED and china:
    relays = sorted(china, key=lambda x: x.get("latency", 9999))[:RELAY_MAX_RELAYS]
    remaining = list(foreign)
    confirmed: List[Dict] = []
    for relay in relays:
      if not remaining:
        break
      batch = remaining
      if RELAY_MAX_PER_RELAY > 0:
        batch = remaining[:RELAY_MAX_PER_RELAY]
      relay_latency = relay.get("latency", 0) or 0
      print(
        f"  relay {relay.get('name', '')} ({relay_latency}ms) "
        f"-> testing {len(batch)} remaining"
      )
      got = mihomo.test_nodes_relay(batch, relay, relay_latency)
      got_ids = {id(n) for n in got}
      confirmed.extend(got)
      remaining = [n for n in remaining if id(n) not in got_ids]
      print(f"    confirmed {len(confirmed)} total, {len(remaining)} left")
    foreign = confirmed
    if not foreign:
      # No foreign node reachable via any relay: fall back to stage-1 foreign
      # so the run still produces output (with the caveat it is US-tested).
      print("  WARN 0 nodes reachable via relay; falling back to stage-1 foreign")
      foreign = [n for n in valid if id(n) not in china_ids]
  else:
    print("  no China relay available; skipping stage-2 (using stage-1 results)")

  final = list(foreign)
  if not EXCLUDE_CN_OUTPUT:
    final.extend(china)
  final.sort(key=lambda x: x.get("latency", 9999))
  return final
