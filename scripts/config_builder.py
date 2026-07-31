#!/usr/bin/env python3
"""
配置构建器 - 负责构建 mihomo 测试配置
符合 SRP: 单一职责，只负责配置生成
"""

from typing import Dict, List, Optional, Tuple

import yaml

from scripts.clash_converter import to_clash_node


class ConfigBuilder:
    """构建 mihomo 测试配置文件"""

    def build_test_config(
        self,
        nodes: List[Dict],
        port: int,
        relay_node: Optional[Dict] = None,
    ) -> Tuple[Dict, Dict[str, Dict], List[int]]:
        """
        构建测试配置

        Returns:
            (config, proxy_to_node, proxy_node_indices)
        """
        clash_proxies: List[Dict] = []
        proxy_to_node: Dict[str, Dict] = {}
        proxy_node_indices: List[int] = []
        relay_name = None

        if relay_node is not None:
            try:
                clash_proxies.append(to_clash_node({**relay_node, "name": "RELAY"}))
                relay_name = "RELAY"
            except (KeyError, ValueError, TypeError):
                relay_name = None

        for i, n in enumerate(nodes):
            synthetic = dict(n)
            synthetic["name"] = f"node-{i}"
            try:
                clash = to_clash_node(synthetic)
                if relay_name:
                    clash["dialer-proxy"] = relay_name
                clash_proxies.append(clash)
                proxy_to_node[f"node-{i}"] = n
                proxy_node_indices.append(i)
            except (KeyError, ValueError, TypeError):
                continue

        config = {
            "external-controller": f"127.0.0.1:{port}",
            "secret": "",
            "mode": "rule",
            "log-level": "silent",
            "geo-auto-update": False,
            "proxies": clash_proxies,
            "proxy-groups": [
                {
                    "name": "TEST",
                    "type": "select",
                    "proxies": ["DIRECT"] + [p["name"] for p in clash_proxies],
                }
            ],
            "rules": ["MATCH,TEST"],
        }
        return config, proxy_to_node, proxy_node_indices

    def write_config(self, config: Dict, path) -> None:
        """将配置写入 YAML 文件"""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False, indent=2)
