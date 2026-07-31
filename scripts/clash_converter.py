#!/usr/bin/env python3
"""
Clash 节点转换器 - SRP: 只负责节点 ↔ Clash 格式/URI 的双向转换

从 output.py 中提取，解除 config_builder 对 output 的依赖（DIP）。
"""

import base64
import json
import urllib.parse
from typing import Dict, List, Optional


def normalize_alpn(val) -> Optional[List[str]]:
  """mihomo 要求 alpn 为 list；URI/JSON 里常是逗号分隔字符串。"""
  if not val:
    return None
  if isinstance(val, list):
    return val
  if isinstance(val, str):
    return [s.strip() for s in val.split(",") if s.strip()]
  return None


def _apply_transport(base: Dict, node: Dict):
  """应用 ws/grpc/h2 传输层配置和 alpn。vmess/vless/trojan 共用，避免重复逻辑。"""
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


def to_clash_node(node: Dict) -> Dict:
  """内部节点 → Clash proxy 格式"""
  ptype = node.get("type", "").lower()
  base = {
    "name": node["name"],
    "type": ptype,
    "server": node["server"],
    "port": str(int(node["port"])),
  }

  if node.get("udp"):
    base["udp"] = True

  if ptype == "ss":
    base["cipher"] = node.get("cipher", "aes-256-gcm")
    base["password"] = node.get("password", "")

  elif ptype == "ssr":
    base["cipher"] = node.get("cipher", "aes-256-cfb")
    base["password"] = node.get("password", "")
    base["protocol"] = node.get("protocol", "origin")
    base["obfs"] = node.get("obfs", "plain")
    if node.get("protocol-param"):
      base["protocol-param"] = node["protocol-param"]
    if node.get("obfs-param"):
      base["obfs-param"] = node["obfs-param"]

  elif ptype == "vmess":
    base["uuid"] = node.get("uuid", "")
    base["alterId"] = int(node.get("alterId", 0))
    base["cipher"] = node.get("security", "auto")
    if node.get("tls"):
      base["tls"] = True
      sni = node.get("sni") or node.get("servername")
      if sni:
        base["servername"] = sni
    if "skip-cert-verify" in node:
      base["skip-cert-verify"] = node["skip-cert-verify"]
    _apply_transport(base, node)

  elif ptype == "trojan":
    base["password"] = node.get("password", "")
    if node.get("sni"):
      base["sni"] = node["sni"]
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    _apply_transport(base, node)

  elif ptype == "vless":
    base["uuid"] = node.get("uuid", "")
    if node.get("flow"):
      base["flow"] = node["flow"]
    sni = node.get("sni") or node.get("servername")
    if sni:
      base["servername"] = sni
    reality = node.get("reality-opts") or {}
    if reality.get("public-key"):
      base["tls"] = True
      base["reality-opts"] = reality
      base["client-fingerprint"] = node.get("client-fingerprint", "chrome")
    elif node.get("tls"):
      base["tls"] = True
    if "skip-cert-verify" in node:
      base["skip-cert-verify"] = node["skip-cert-verify"]
    _apply_transport(base, node)

  elif ptype == "hysteria2":
    base["password"] = node.get("password", "")
    if node.get("sni"):
      base["sni"] = node["sni"]
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True
    if node.get("obfs"):
      base["obfs"] = node["obfs"]
    if node.get("obfs-password"):
      base["obfs-password"] = node["obfs-password"]
    if node.get("up"):
      base["up"] = node["up"]
    if node.get("down"):
      base["down"] = node["down"]
    alpn = normalize_alpn(node.get("alpn"))
    if alpn:
      base["alpn"] = alpn

  elif ptype in ("http", "socks5"):
    if node.get("username"):
      base["username"] = node["username"]
    if node.get("password"):
      base["password"] = node["password"]
    if node.get("tls"):
      base["tls"] = True
    if node.get("skip-cert-verify"):
      base["skip-cert-verify"] = True

  return base


def _b64(s: str) -> str:
  return base64.b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")


def _frag(name: str) -> str:
  return urllib.parse.quote(name or "", safe="")


def _qval(v) -> str:
  return urllib.parse.quote(str(v), safe="")


def _query(params: Dict) -> str:
  return "&".join(f"{k}={_qval(v)}" for k, v in params.items() if v not in (None, ""))


def to_uri(node: Dict) -> Optional[str]:
  """内部节点 → URI 字符串"""
  ptype = node.get("type", "").lower()
  server = node.get("server", "")
  port = node.get("port", "")
  name = node.get("name", "")
  if not server or not port:
    return None
  try:
    if ptype == "ss":
      cipher = node.get("cipher", "aes-256-gcm")
      password = node.get("password", "")
      return f"ss://{_b64(f'{cipher}:{password}')}@{server}:{port}#{_frag(name)}"

    if ptype == "vmess":
      cfg = {
        "v": "2", "ps": name, "add": server, "port": str(port),
        "id": node.get("uuid", ""), "aid": str(node.get("alterId", 0)),
        "scy": node.get("security", "auto"), "net": node.get("network", "tcp"),
        "type": node.get("headerType", "none"), "host": node.get("host", ""),
        "path": node.get("path", ""), "tls": node.get("tls", ""),
        "sni": node.get("sni", ""), "alpn": node.get("alpn", ""),
      }
      return "vmess://" + _b64(json.dumps(cfg, ensure_ascii=False, indent=2))

    if ptype == "vless":
      params: Dict = {"encryption": "none"}
      reality = node.get("reality-opts") or {}
      if reality.get("public-key"):
        params["security"] = "reality"
        params["sni"] = node.get("sni", "")
        params["flow"] = node.get("flow", "")
        params["type"] = node.get("network", "tcp")
        params["host"] = node.get("host", "")
        params["path"] = node.get("path", "")
        params["pbk"] = reality.get("public-key", "")
        params["sid"] = reality.get("short-id", "")
        params["fp"] = node.get("client-fingerprint", "chrome")
      else:
        if node.get("security") == "tls" or node.get("tls"):
          params["security"] = "tls"
        params["sni"] = node.get("sni", "")
        params["flow"] = node.get("flow", "")
        net = node.get("network", "tcp")
        if net and net != "tcp":
          params["type"] = net
        params["host"] = node.get("host", "")
        params["path"] = node.get("path", "")
      if node.get("alpn"):
        params["alpn"] = node["alpn"]
      q = _query(params)
      return f"vless://{node.get('uuid', '')}@{server}:{port}?{q}#{_frag(name)}"

    if ptype == "trojan":
      params: Dict = {}
      if node.get("sni"):
        params["security"] = "tls"
        params["sni"] = node["sni"]
      net = node.get("network", "tcp")
      if net and net != "tcp":
        params["type"] = net
      params["host"] = node.get("host", "")
      params["path"] = node.get("path", "")
      if node.get("alpn"):
        params["alpn"] = node["alpn"]
      if node.get("skip-cert-verify"):
        params["allowInsecure"] = "1"
      q = _query(params)
      prefix = f"trojan://{node.get('password', '')}@{server}:{port}"
      return f"{prefix}?{q}#{_frag(name)}" if q else f"{prefix}#{_frag(name)}"

    if ptype == "hysteria2":
      params: Dict = {}
      if node.get("sni"):
        params["sni"] = node["sni"]
      if node.get("obfs"):
        params["obfs"] = node["obfs"]
      if node.get("obfs-password"):
        params["obfs-password"] = node["obfs-password"]
      if node.get("insecure") or node.get("skip-cert-verify"):
        params["insecure"] = "1"
      if node.get("up"):
        params["up"] = node["up"]
      if node.get("down"):
        params["down"] = node["down"]
      if node.get("alpn"):
        params["alpn"] = node["alpn"]
      q = _query(params)
      prefix = f"hysteria2://{node.get('password', '')}@{server}:{port}"
      return f"{prefix}?{q}#{_frag(name)}" if q else f"{prefix}#{_frag(name)}"

    if ptype == "ssr":
      password_b64 = _b64(node.get("password", ""))
      main = f"{server}:{port}:{node.get('protocol', 'origin')}:{node.get('cipher', 'aes-256-cfb')}:{node.get('obfs', 'plain')}:{password_b64}"
      extra: Dict = {}
      if node.get("obfs-param"):
        extra["obfsparam"] = _b64(node["obfs-param"])
      if node.get("protocol-param"):
        extra["protoparam"] = _b64(node["protocol-param"])
      if name:
        extra["remarks"] = _b64(name)
      if extra:
        main += "/?" + _query(extra)
      return "ssr://" + _b64(main)

  except Exception:
    return None
  return None