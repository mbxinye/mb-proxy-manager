#!/usr/bin/env python3
"""
SS/SSR 协议解析器 - SRP: 只负责 SS/SSR 解析
"""

import base64
import urllib.parse
from typing import Dict, Optional

from scripts.parsers.base import BaseProtocolParser


class SSParser(BaseProtocolParser):
    """Shadowsocks 协议解析器"""
    
    def supports(self, uri: str) -> bool:
        return uri.startswith("ss://")
    
    def parse(self, url: str) -> Optional[Dict]:
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
        except Exception as e:
            print(f"  ⚠ SS 解析失败: {url[:50]}... ({e})")
            return None
    
    @staticmethod
    def _try_base64_decode(content: str) -> Optional[str]:
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


class SSRParser(BaseProtocolParser):
    """ShadowsocksR 协议解析器"""
    
    def supports(self, uri: str) -> bool:
        return uri.startswith("ssr://")
    
    def parse(self, url: str) -> Optional[Dict]:
        try:
            content = url[6:]
            decoded = SSParser._try_base64_decode(content)
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
        except Exception as e:
            print(f"  ⚠ SSR 解析失败: {url[:50]}... ({e})")
            return None
