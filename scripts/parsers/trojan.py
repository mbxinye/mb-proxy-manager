#!/usr/bin/env python3
"""
Trojan/Hysteria2 协议解析器 - SRP: 只负责 Trojan/Hysteria2 解析
"""

import urllib.parse
from typing import Dict, Optional

from scripts.parsers.base import BaseProtocolParser


class TrojanParser(BaseProtocolParser):
    """Trojan 协议解析器"""
    
    def supports(self, uri: str) -> bool:
        return uri.startswith("trojan://")
    
    def parse(self, url: str) -> Optional[Dict]:
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
        except Exception as e:
            print(f"  ⚠ Trojan 解析失败: {url[:50]}... ({e})")
            return None


class Hysteria2Parser(BaseProtocolParser):
    """Hysteria2 协议解析器"""
    
    def supports(self, uri: str) -> bool:
        return uri.startswith("hysteria2://") or uri.startswith("hy2://")
    
    def parse(self, url: str) -> Optional[Dict]:
        try:
            parsed = urllib.parse.urlparse(url)
            server = parsed.hostname
            password = parsed.username or ""
            if not server:
                return None
            query = urllib.parse.parse_qs(parsed.query)
            name = parsed.fragment or query.get("remarks", [f"Hysteria2_{server[:15]}"])[0]
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
            if query.get("insecure", ["0"])[0] == "1":
                node["skip-cert-verify"] = True
            obfs = query.get("obfs", [None])[0]
            if obfs:
                node["obfs"] = obfs
                obfs_pwd = query.get("obfs-password", [None])[0]
                if obfs_pwd:
                    node["obfs-password"] = obfs_pwd
            up = query.get("up", [None])[0]
            if up:
                node["up"] = up
            down = query.get("down", [None])[0]
            if down:
                node["down"] = down
            alpn = query.get("alpn", [None])[0]
            if alpn:
                node["alpn"] = alpn
            return node
        except Exception as e:
            print(f"  ⚠ Hysteria2 解析失败: {url[:50]}... ({e})")
            return None
