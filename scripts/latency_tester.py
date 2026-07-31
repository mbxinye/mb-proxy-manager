#!/usr/bin/env python3
"""
延迟测试器 - 负责通过 mihomo API 执行延迟测试
符合 SRP: 单一职责，只负责测试结果收集
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from scripts.config import MAX_LATENCY, MIHOMO_TEST_TIMEOUT, MIHOMO_TEST_URL, PROXY_TEST_CONCURRENCY
from scripts.utils import get_local_opener


class LatencyTester:
    """通过 mihomo API 执行并发延迟测试"""

    def __init__(
        self,
        port: int,
        proxy_to_node: Dict[str, Dict],
        concurrency: int = PROXY_TEST_CONCURRENCY,
        latency_offset: int = 0,
        latency_cap: int = MAX_LATENCY,
        test_url: str = MIHOMO_TEST_URL,
    ):
        self._port = port
        self._proxy_to_node = proxy_to_node
        self._concurrency = concurrency
        self._latency_offset = latency_offset
        self._latency_cap = latency_cap
        self._test_url = test_url

    def run_tests(self) -> List[Dict]:
        """执行并发延迟测试，返回可用节点列表"""
        base = f"http://127.0.0.1:{self._port}/proxies"
        results: List[Dict] = []
        total = len(self._proxy_to_node)
        latency_dropped = 0

        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            futures = {
                pool.submit(self._test_one, base, name): name
                for name in self._proxy_to_node
            }
            done = 0
            for f in as_completed(futures):
                done += 1
                name = futures[f]
                latency = f.result()
                if latency is not None:
                    adj = latency - self._latency_offset
                    if adj < 1:
                        adj = 1
                    node = self._proxy_to_node[name]
                    node["latency"] = adj
                    if self._latency_cap > 0 and adj > self._latency_cap:
                        latency_dropped += 1
                    else:
                        results.append(node)
                if done % 50 == 0 or done == total:
                    print(f"    进度 {done}/{total}, 可用 {len(results)}")

        if latency_dropped:
            print(f"    延迟超阈值(>{MAX_LATENCY}ms)剔除: {latency_dropped}")
        return results

    def _test_one(self, base: str, name: str) -> Optional[int]:
        """测试单个节点的延迟"""
        from urllib.parse import quote
        url = (
            f"{base}/{quote(name, safe='')}/delay"
            f"?timeout={MIHOMO_TEST_TIMEOUT}&url={quote(self._test_url, safe='')}"
        )
        http_timeout = MIHOMO_TEST_TIMEOUT / 1000 + 3
        try:
            opener = get_local_opener()
            with opener.open(url, timeout=http_timeout) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(resp.read().decode("utf-8"))
                delay = data.get("delay")
                return int(delay) if delay is not None else None
        except Exception:
            return None
