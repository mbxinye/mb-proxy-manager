#!/usr/bin/env python3
"""
协议解析器基类 - 开闭原则(OCP) + 单一职责(SRP)

每个协议解析器只负责一种协议的解析，新增协议只需添加新类。
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseProtocolParser(ABC):
    """协议解析器基类 - ISP: 接口隔离，每种协议独立接口"""
    
    @abstractmethod
    def parse(self, uri: str) -> Optional[Dict]:
        """解析 URI 返回节点字典"""
        pass
    
    @abstractmethod
    def supports(self, uri: str) -> bool:
        """检查是否支持该 URI 格式"""
        pass
