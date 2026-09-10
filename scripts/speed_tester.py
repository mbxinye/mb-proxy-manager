#!/usr/bin/env python3
"""带宽测速器 - SRP：只负责经 mihomo 出网测量每个节点的实际吞吐。

延迟低不代表能用：免费节点最常见的问题是握手快但带宽不足 1Mbps。
做法是逐个把 selector 切到目标节点，再经 mixed-port 下载固定大小的测速文件。
"""

import json
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from scripts.config import SPEED_MAX_BYTES, SPEED_TIMEOUT, SPEED_URL
from scripts.fetcher import USER_AGENT
from scripts.log import get_logger

log = get_logger("speed")

_CHUNK = 65536


class SpeedTester:
    """经 mihomo mixed-port 逐节点测下载吞吐。

    串行是刻意的：并发下载会让节点互相抢带宽，测出来的数字不可比。
    """

    def __init__(
        self,
        api_port: int,
        http_port: int,
        proxy_to_node: Dict[str, Dict],
        timeout: int = SPEED_TIMEOUT,
        max_bytes: int = SPEED_MAX_BYTES,
        url: str = SPEED_URL,
    ):
        self._api_port = api_port
        self._http_port = http_port
        self._proxy_to_node = proxy_to_node
        self._timeout = timeout
        self._max_bytes = max_bytes
        self._url = url

    def run(self, names: List[str]) -> Dict[str, float]:
        """返回 {proxy_name: mbps}，测不出速度的节点不出现在结果里。"""
        results: Dict[str, float] = {}
        total = len(names)
        for i, name in enumerate(names, 1):
            mbps = self._measure_one(name)
            if mbps is not None:
                results[name] = mbps
                self._proxy_to_node[name]["speed_mbps"] = round(mbps, 2)
            if i % 10 == 0 or i == total:
                log.info(f"    测速 {i}/{total}, 有效 {len(results)}")
        return results

    def _switch(self, name: str) -> bool:
        """把 TEST selector 切到指定节点。"""
        from urllib.parse import quote

        req = urllib.request.Request(
            f"http://127.0.0.1:{self._api_port}/proxies/TEST",
            data=json.dumps({"name": name}).encode("utf-8"),
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 - 固定 127.0.0.1
                return resp.status == 204 or resp.status == 200
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return False

    def _measure_one(self, name: str) -> Optional[float]:
        if not self._switch(name):
            return None

        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(
                {"http": f"http://127.0.0.1:{self._http_port}", "https": f"http://127.0.0.1:{self._http_port}"}
            )
        )
        try:
            # 必须带 UA：Cloudflare 测速端点对无 UA 请求直接 403，会收到 0 字节。
            req = urllib.request.Request(self._url, headers={"User-Agent": USER_AGENT})
            # open() 返回后才开始计时，把 TLS/连接建立排除在吞吐计算之外，
            # 否则握手慢的节点会被重复惩罚（延迟已经单独筛过一轮）。
            # 连接时限单独放宽：高延迟节点光握手就要几秒，与测量窗口共用 timeout
            # 会让它们一个字节都拿不到，被误判成"测不出速度"。
            with opener.open(req, timeout=self._timeout * 2) as resp:
                start = time.monotonic()
                received = 0
                while received < self._max_bytes:
                    if time.monotonic() - start > self._timeout:
                        break
                    chunk = resp.read(_CHUNK)
                    if not chunk:
                        break
                    received += len(chunk)
                elapsed = time.monotonic() - start
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

        if received == 0 or elapsed <= 0:
            return None
        return received * 8 / elapsed / 1_000_000
