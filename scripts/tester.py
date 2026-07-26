#!/usr/bin/env python3

from typing import Dict, List

from scripts import mihomo
from scripts.config import (
  EXCLUDE_CN_OUTPUT,
  RELAY_ENABLED,
  RELAY_MAX_PER_RELAY,
  RELAY_MAX_RELAYS,
)
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

  print(f"  \u6b63\u5728\u6d4b\u8bd5 {len(complete)} \u4e2a\u8282\u70b9 (mihomo \u7aef\u5230\u7aef)...")

  valid = mihomo.test_nodes(complete)

  # Stage-1 done: `valid` holds directly-reachable nodes (from US runner).

  # Split into China relays and foreign exit nodes (by object identity).
  china = [
    n for n in valid
    if is_china_node(
      n.get("name", ""),
      n.get("server", ""),
      n.get("sni", "") or n.get("servername", "") or "",
    )
  ]
  china_ids = {id(n) for n in china}
  foreign = [n for n in valid if id(n) not in china_ids]
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
