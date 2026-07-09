#!/usr/bin/env python3

from typing import Dict, List

from scripts import mihomo


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

  valid.sort(key=lambda x: x.get("latency", 9999))
  return valid
