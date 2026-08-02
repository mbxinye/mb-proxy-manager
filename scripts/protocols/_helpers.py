#!/usr/bin/env python3
"""协议无关的编解码与传输层辅助函数（DRY：消除各协议解析器中的重复逻辑）。"""

import base64
import binascii
import urllib.parse
from typing import Dict, List, Optional


def try_base64_decode(content: str) -> Optional[str]:
  """宽松 Base64 解码：自动补 padding、URL 解码、长度启发过滤乱码。"""
  try:
    if "%" in content:
      try:
        content = urllib.parse.unquote(content)
      except (ValueError, urllib.parse.InvalidURL):
        pass
    padding = len(content) % 4
    if padding > 0:
      content += "=" * (4 - padding)
    decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
    if decoded and len(decoded) > len(content) / 2:
      return decoded
  except (ValueError, binascii.Error, UnicodeDecodeError):
    pass
  return None


def normalize_alpn(val) -> Optional[List[str]]:
  """mihomo 要求 alpn 为 list；URI/JSON 里常是逗号分隔字符串。"""
  if not val:
    return None
  if isinstance(val, list):
    return val
  if isinstance(val, str):
    return [s.strip() for s in val.split(",") if s.strip()]
  return None


def apply_transport(base: Dict, node: Dict) -> None:
  """应用 ws/grpc/h2 传输层配置和 alpn（vmess/vless/trojan 共用）。"""
  network = node.get("network", "tcp")
  if network in ("ws", "websocket"):
    base["network"] = "ws"
    if node.get("ws-opts"):
      base["ws-opts"] = node["ws-opts"]
    else:
      ws_opts: Dict = {}
      if node.get("path"):
        ws_opts["path"] = node["path"]
      if node.get("host"):
        ws_opts["headers"] = {"Host": node["host"]}
      if ws_opts:
        base["ws-opts"] = ws_opts
  elif network == "grpc":
    base["network"] = "grpc"
    if node.get("grpc-opts"):
      base["grpc-opts"] = node["grpc-opts"]
  elif network == "h2":
    base["network"] = "h2"
    if node.get("h2-opts"):
      base["h2-opts"] = node["h2-opts"]
  alpn = normalize_alpn(node.get("alpn"))
  if alpn:
    base["alpn"] = alpn


def base_proxy(node: Dict) -> Dict:
  """Clash proxy 公共字段（name/type/server/port/udp），各协议在其上叠加专属字段。"""
  base = {
    "name": node["name"],
    "type": node.get("type", "").lower(),
    "server": node["server"],
    "port": str(int(node["port"])),
  }
  if node.get("udp"):
    base["udp"] = True
  return base


def get_sni(node: Dict) -> Optional[str]:
  """统一访问 SNI（兼容 sni / servername 两种字段名），消除 5 处重复兼容逻辑。"""
  return node.get("sni") or node.get("servername")


def b64encode(s: str) -> str:
  return base64.b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")


def b64decode_str(s: str) -> str:
  """严格 Base64 解码（自动补 padding），用于 SSR 密码等必须成功的场景。"""
  return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", errors="ignore")


def url_fragment(name: str) -> str:
  return urllib.parse.quote(name or "", safe="")


def url_qval(v) -> str:
  return urllib.parse.quote(str(v), safe="")


def build_query(params: Dict) -> str:
  return "&".join(f"{k}={url_qval(v)}" for k, v in params.items() if v not in (None, ""))
