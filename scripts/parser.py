#!/usr/bin/env python3

import base64
import json
import urllib.parse
from typing import Dict, List, Optional

import yaml


class NodeParser:

  def __init__(self):
    self._skipped = 0

  def parse_subscription(self, content: str) -> List[Dict]:
    nodes = []
    content = content.strip()
    if not content:
      return nodes

    # Only try base64 decode on the full content if it doesn't contain URI schemes
    has_uri_schemes = "://" in content
    if not has_uri_schemes:
      decoded = self._try_base64_decode(content)
      if decoded:
        content = decoded

    # Clash 配置判定：全文扫描 proxies:/proxy-groups: 关键字。
    # 旧逻辑只看前 30 行，完整 Clash 配置（mixed-port 开头）的 proxies: 常在第 50-200 行，
    # 会漏判走 URI 逐行分支，把整个 YAML 当文本逐行 skip（单订阅可误杀上万行）。
    if "proxies:" in content or "proxy-groups:" in content:
      nodes = self._parse_yaml(content)
    else:
      for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith(("#", "//")):
          continue
        node = self.parse_uri(line)
        if node:
          nodes.append(node)
        else:
          self._skipped += 1
    return nodes

  def _try_base64_decode(self, content: str) -> Optional[str]:
    try:
      if "%" in content:
        try:
          content = urllib.parse.unquote(content)
        except Exception:
          pass
      padding = len(content) % 4
      if padding > 0:
        content += "=" * (4 - padding)
      decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
      if decoded and len(decoded) > len(content) / 2:
        return decoded
    except Exception:
      pass
    return None

  def _parse_yaml(self, content: str) -> List[Dict]:
    nodes = []
    try:
      data = yaml.safe_load(content)
      if not isinstance(data, dict):
        return nodes
      proxies = data.get("proxies", []) or []
      for proxy in proxies:
        if not isinstance(proxy, dict):
          continue
        node = self._proxy_to_node(proxy)
        if node:
          nodes.append(node)
    except Exception:
      pass
    return nodes

  def _proxy_to_node(self, proxy: Dict) -> Optional[Dict]:
    try:
      ptype = proxy.get("type", "").lower()
      name = proxy.get("name", "Unknown")[:50]
      server = proxy.get("server", "")
      port = proxy.get("port", 0)
      if not server or not port:
        return None

      node: Dict = {
        "type": ptype,
        "name": name,
        "server": server,
        "port": int(port),
      }
      # 字段白名单覆盖各协议必需字段：ssr(protocol/obfs/param)、
      # hysteria2(obfs/up/down)、grpc/h2 传输、alpn 等。缺失会导致输出残缺节点连接失败。
      for field in [
        "uuid", "password", "cipher", "alterId", "network", "tls", "sni", "flow",
        "udp", "ws-opts", "servername", "client-fingerprint", "skip-cert-verify",
        "username",
        "protocol", "obfs", "protocol-param", "obfs-param",
        "grpc-opts", "h2-opts", "alpn",
        "obfs-password", "insecure", "up", "down",
      ]:
        if field in proxy:
          node[field] = proxy[field]
      if ptype == "vmess":
        node["security"] = proxy.get("cipher", "auto")
      elif ptype == "vless":
        if "reality-opts" in proxy:
          node["reality-opts"] = proxy["reality-opts"]
          node["client-fingerprint"] = proxy.get("client-fingerprint", "chrome")
      elif ptype == "trojan":
        node["skip-cert-verify"] = proxy.get("skip-cert-verify", False)
      return node
    except Exception:
      return None

  def parse_uri(self, line: str) -> Optional[Dict]:
    try:
      if line.startswith("ss://"):
        return self._parse_ss(line)
      elif line.startswith("vmess://"):
        return self._parse_vmess(line)
      elif line.startswith("trojan://"):
        return self._parse_trojan(line)
      elif line.startswith("vless://"):
        return self._parse_vless(line)
      elif line.startswith("hysteria2://") or line.startswith("hy2://"):
        return self._parse_hysteria2(line)
      elif line.startswith("ssr://"):
        return self._parse_ssr(line)
    except Exception:
      pass
    return None

  def _parse_ss(self, url: str) -> Optional[Dict]:
    try:
      rest = url[5:]
      remark = ""
      if "#" in rest:
        rest, remark = rest.split("#", 1)
        remark = urllib.parse.unquote(remark)

      # Old format: ss://BASE64(method:password)@server:port
      if "@" in rest:
        b64_part, server_port = rest.split("@", 1)
        decoded = self._try_base64_decode(b64_part)
        if decoded:
          method_pass = decoded
        else:
          method_pass = b64_part
        if ":" not in method_pass or ":" not in server_port:
          return None
        method, password = method_pass.split(":", 1)
        server, port_str = server_port.rsplit(":", 1)
      else:
        # SIP008 format: ss://BASE64(method:password@server:port)
        decoded = self._try_base64_decode(rest)
        if not decoded:
          return None
        if "@" not in decoded:
          return None
        method_pass, server_port = decoded.split("@", 1)
        if ":" not in method_pass or ":" not in server_port:
          return None
        method, password = method_pass.split(":", 1)
        server, port_str = server_port.rsplit(":", 1)

      return {
        "type": "ss",
        "name": remark[:50] or f"SS_{server[:15]}",
        "server": server,
        "port": int(port_str),
        "password": password,
        "cipher": method,
      }
    except Exception:
      return None

  def _parse_ssr(self, url: str) -> Optional[Dict]:
    try:
      content = url[6:]
      decoded = self._try_base64_decode(content)
      if not decoded:
        return None
      parts = decoded.split(":")
      if len(parts) < 6:
        return None
      server = parts[0]
      port = int(parts[1])
      protocol = parts[2]
      cipher = parts[3]
      obfs = parts[4]
      password_b64 = parts[5]
      password = ""
      try:
        password = base64.b64decode(password_b64 + "=" * (4 - len(password_b64) % 4)).decode()
      except Exception:
        password = password_b64
      params = ""
      obfs_param = ""
      if "/?" in decoded:
        query_str = decoded.split("/?")[1]
        qs = urllib.parse.parse_qs(query_str)
        params = qs.get("protoparam", [""])[0]
        obfs_param = qs.get("obfsparam", [""])[0]
      return {
        "type": "ssr",
        "name": f"SSR_{server[:15]}",
        "server": server,
        "port": port,
        "password": password,
        "cipher": cipher,
        "protocol": protocol,
        "obfs": obfs,
        "protocol-param": params,
        "obfs-param": obfs_param,
      }
    except Exception:
      return None

  def _parse_vmess(self, url: str) -> Optional[Dict]:
    try:
      content = url[8:]
      decoded = self._try_base64_decode(content)
      if not decoded:
        return None
      config = json.loads(decoded)
      node = {
        "type": "vmess",
        "name": config.get("ps", "VMess")[:50],
        "server": config.get("add", ""),
        "port": int(config.get("port", 443)),
        "uuid": config.get("id", ""),
        "alterId": int(config.get("aid", 0)),
        "security": config.get("scy", "auto"),
        "network": config.get("net", "tcp"),
        "tls": config.get("tls", ""),
      }
      for short, long in [("p", "path"), ("host", "host"), ("sni", "sni"), ("fp", "client-fingerprint"), ("alpn", "alpn")]:
        val = config.get(long) or config.get(short)
        if val:
          node[long] = val
      return node
    except Exception:
      return None

  def _parse_trojan(self, url: str) -> Optional[Dict]:
    try:
      parsed = urllib.parse.urlparse(url)
      server = parsed.hostname
      password = parsed.username or ""
      if not server:
        return None
      query = urllib.parse.parse_qs(parsed.query)
      name = parsed.fragment or query.get("remarks", [f"Trojan_{server[:15]}"])[0]
      if name:
        name = urllib.parse.unquote(name)
      node: Dict = {
        "type": "trojan",
        "name": name[:50],
        "server": server,
        "port": parsed.port or 443,
        "password": password,
      }
      if query.get("sni", [None])[0]:
        node["sni"] = query["sni"][0]
      net = query.get("type", [None])[0] or query.get("network", [None])[0]
      if net:
        node["network"] = net
      if query.get("path", [None])[0]:
        node["path"] = query["path"][0]
      if query.get("host", [None])[0]:
        node["host"] = query["host"][0]
      if query.get("alpn", [None])[0]:
        node["alpn"] = query["alpn"][0]
      node["skip-cert-verify"] = query.get("allowInsecure", ["0"])[0] == "1"
      return node
    except Exception:
      return None

  def _parse_vless(self, url: str) -> Optional[Dict]:
    try:
      parsed = urllib.parse.urlparse(url)
      server = parsed.hostname
      uuid = parsed.username or ""
      if not server:
        return None
      query = urllib.parse.parse_qs(parsed.query)
      name = parsed.fragment or query.get("remarks", [f"VLESS_{server[:15]}"])[0]
      if name:
        name = urllib.parse.unquote(name)
      security = query.get("security", [""])[0]
      node: Dict = {
        "type": "vless",
        "name": name[:50],
        "server": server,
        "port": parsed.port or 443,
        "uuid": uuid,
        "flow": query.get("flow", [None])[0],
        "security": security,
      }
      if security in ("tls", "reality"):
        node["tls"] = True
      if security == "reality":
        node["reality-opts"] = {
          "public-key": query.get("pbk", [""])[0],
          "short-id": query.get("sid", [""])[0],
        }
        node["client-fingerprint"] = query.get("fp", ["chrome"])[0]
      elif security == "tls":
        node["client-fingerprint"] = query.get("fp", ["chrome"])[0]
      if query.get("sni", [None])[0]:
        node["sni"] = query["sni"][0]
      net = query.get("type", [None])[0] or query.get("network", [None])[0]
      if net:
        node["network"] = net
      if query.get("headerType", [None])[0]:
        node["headerType"] = query["headerType"][0]
      if query.get("host", [None])[0]:
        node["host"] = query["host"][0]
      if query.get("path", [None])[0]:
        node["path"] = query["path"][0]
      if query.get("alpn", [None])[0]:
        node["alpn"] = query["alpn"][0]
      return node
    except Exception:
      return None

  def _parse_hysteria2(self, url: str) -> Optional[Dict]:
    try:
      parsed = urllib.parse.urlparse(url)
      server = parsed.hostname
      password = parsed.username or ""
      if not server:
        return None
      query = urllib.parse.parse_qs(parsed.query)
      name = parsed.fragment or query.get("remarks", [f"Hy2_{server[:15]}"])[0]
      if name:
        name = urllib.parse.unquote(name)
      node: Dict = {
        "type": "hysteria2",
        "name": name[:50],
        "server": server,
        "port": parsed.port or 443,
        "password": password,
      }
      if query.get("sni", [None])[0]:
        node["sni"] = query["sni"][0]
      if query.get("obfs", [None])[0]:
        node["obfs"] = query["obfs"][0]
      if query.get("obfs-password", [None])[0]:
        node["obfs-password"] = query["obfs-password"][0]
      if query.get("insecure", ["0"])[0] == "1":
        node["skip-cert-verify"] = True
      if query.get("up", [None])[0]:
        node["up"] = query["up"][0]
      if query.get("down", [None])[0]:
        node["down"] = query["down"][0]
      if query.get("alpn", [None])[0]:
        node["alpn"] = query["alpn"][0]
      return node
    except Exception:
      return None


def parse_all(results: List[dict]) -> List[Dict]:
  parser = NodeParser()
  all_nodes: List[Dict] = []
  per_url_skip = []
  for r in results:
    if not r["success"] or not r.get("content"):
      continue
    before = parser._skipped
    nodes = parser.parse_subscription(r["content"])
    delta = parser._skipped - before
    if delta > 0:
      per_url_skip.append((r["url"], delta))
    for n in nodes:
      n["_sub_url"] = r["url"]
    all_nodes.extend(nodes)
  print(f"  \u89e3\u6790\u5b8c\u6210: {len(all_nodes)} \u4e2a\u8282\u70b9")
  if parser._skipped:
    print(f"  \u89e3\u6790\u8df3\u8fc7: {parser._skipped} \u884c\u65e0\u6548/\u4e0d\u652f\u6301")
    print("  \u8df3\u8fc7\u660e\u7ec6 (URL | skip\u6570):")
    for url, n in sorted(per_url_skip, key=lambda x: -x[1]):
      print(f"    [{n:>6}] {url[:60]}")
  return all_nodes
