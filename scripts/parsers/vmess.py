#!/usr/bin/env python3
"""
VMess/VLESS 协议解析器 - SRP: 只负责 VMess/VLESS 解析
"""

import json
import urllib.parse
from typing import Dict, Optional

from scripts.parsers.base import BaseProtocolParser


class VMessParser(BaseProtocolParser):
    """VMess 协议解析器"""
    
    def supports(self, uri: str) -> bool:
        return uri.startswith("vmess://")
    
    def parse(self, url: str) -> Optional[Dict]:
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
        except Exception as e:
            print(f"  ⚠ VMess 解析失败: {url[:50]}... ({e})")
            return None
    
    @staticmethod
    def _try_base64_decode(content: str) -> Optional[str]:
        import base64
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


class VLESSParser(BaseProtocolParser):
    """VLESS 协议解析器"""
    
    def supports(self, uri: str) -> bool:
        return uri.startswith("vless://")
    
    def parse(self, url: str) -> Optional[Dict]:
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
            }
            if security == "xtls":
                node["flow"] = query.get("flow", [None])[0] or ""
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
            if security == "reality":
                reality_opts = {}
                pk = query.get("pbk", [None])[0]
                if pk:
                    reality_opts["public-key"] = pk
                sid = query.get("sid", [None])[0]
                if sid:
                    reality_opts["short-id"] = sid
                spx = query.get("spx", [""])[0]
                if spx:
                    reality_opts["spider-x"] = spx
                if reality_opts:
                    node["reality-opts"] = reality_opts
                node["client-fingerprint"] = query.get("fp", ["chrome"])[0]
            elif security == "tls":
                node["tls"] = True
            node["skip-cert-verify"] = query.get("allowInsecure", ["0"])[0] == "1"
            return node
        except Exception as e:
            print(f"  ⚠ VLESS 解析失败: {url[:50]}... ({e})")
            return None
