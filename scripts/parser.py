#!/usr/bin/env python3
"""
节点解析器 - 使用策略模式，符合 OCP + SRP
"""

from typing import Dict, List, Optional

import yaml

from scripts.parsers.registry import get_registry


class NodeParser:
    """节点解析器 - 委托给协议解析器和 YAML 解析器"""
    
    def __init__(self):
        self._skipped = 0
        self._registry = get_registry()
    
    def parse_subscription(self, content: str) -> List[Dict]:
        """解析订阅内容"""
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
        if "proxies:" in content or "proxy-groups:" in content:
            nodes = self._parse_yaml(content)
        else:
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith(("#", "//")):
                    continue
                node = self._registry.parse(line)
                if node:
                    nodes.append(node)
                else:
                    self._skipped += 1
        return nodes
    
    def _try_base64_decode(self, content: str) -> Optional[str]:
        """尝试 Base64 解码"""
        import base64
        import urllib.parse
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
        """解析 Clash YAML 配置"""
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
        except Exception as e:
            print(f"  ⚠ YAML 解析失败: {str(e)[:100]}")
        return nodes
    
    def _proxy_to_node(self, proxy: Dict) -> Optional[Dict]:
        """Clash proxy 转内部节点格式"""
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
            # 字段白名单覆盖各协议必需字段
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
        except Exception as e:
            print(f"  ⚠ 节点转换失败: {name} ({e})")
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
