#!/usr/bin/env python3
"""
解析器注册表 - 开闭原则(OCP): 新增协议只需注册，无需修改主逻辑
"""

from typing import Dict, List, Optional

from scripts.parsers.base import BaseProtocolParser


class ParserRegistry:
    """协议解析器注册表"""
    
    def __init__(self):
        self._parsers: List[BaseProtocolParser] = []
    
    def register(self, parser: BaseProtocolParser) -> None:
        """注册解析器"""
        self._parsers.append(parser)
    
    def parse(self, uri: str) -> Optional[Dict]:
        """根据 URI 格式分发到对应解析器"""
        for parser in self._parsers:
            if parser.supports(uri):
                return parser.parse(uri)
        return None
    
    @property
    def parsers(self) -> List[BaseProtocolParser]:
        return list(self._parsers)


# 全局注册表
_registry: Optional[ParserRegistry] = None


def get_registry() -> ParserRegistry:
    """获取全局解析器注册表"""
    global _registry
    if _registry is None:
        _registry = ParserRegistry()
        # 注册所有内置解析器
        from scripts.parsers.ss import SSParser, SSRParser
        from scripts.parsers.vmess import VMessParser, VLESSParser
        from scripts.parsers.trojan import TrojanParser, Hysteria2Parser
        
        _registry.register(SSParser())
        _registry.register(SSRParser())
        _registry.register(VMessParser())
        _registry.register(VLESSParser())
        _registry.register(TrojanParser())
        _registry.register(Hysteria2Parser())
    return _registry
