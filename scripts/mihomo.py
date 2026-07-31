#!/usr/bin/env python3
"""
Mihomo 测试模块 - 协调二进制管理、配置构建、进程管理和延迟测试
符合 DIP: 依赖抽象接口，各组件可独立替换
"""

import re
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from scripts.config import (
    MAX_LATENCY,
    MIHOMO_TEST_TIMEOUT,
    MIHOMO_TEST_URL,
    MIHOMO_VERSION,
    PROXY_TEST_CONCURRENCY,
    RELAY_CONCURRENCY,
)
from scripts.config_builder import ConfigBuilder
from scripts.latency_tester import LatencyTester
from scripts.mihomo_manager import BinaryManager
from scripts.process_manager import ProcessManager


class MihomoTester:
    """mihomo 测试协调器 - 组合各职责类完成端到端测试"""

    def __init__(self, binary_manager: Optional[BinaryManager] = None):
        self._config_builder = ConfigBuilder()
        self._binary_manager = binary_manager or BinaryManager(MIHOMO_VERSION)
        self._binary: Optional[Path] = None

    @property
    def binary(self) -> Path:
        if self._binary is None:
            self._binary = self._binary_manager.ensure_binary()
        return self._binary

    def test_nodes(
        self,
        nodes: List[Dict],
        latency_cap: int = MAX_LATENCY,
        test_url: str = MIHOMO_TEST_URL,
    ) -> List[Dict]:
        """测试节点可用性"""
        if not nodes:
            return []

        print(f"  真实测试 {len(nodes)} 个节点 (并发 {PROXY_TEST_CONCURRENCY})...")

        # 预校验：剔除会让 mihomo fatal 的节点
        valid_config_nodes = self._validate_config(nodes)
        if not valid_config_nodes:
            print("  无配置合法节点")
            return []

        # 单批跑完
        try:
            valid = self._test_batch(valid_config_nodes, latency_cap=latency_cap, test_url=test_url)
        except RuntimeError as e:
            print(f"  ⚠ 单批启动失败，退回分批: {str(e)[:100]}")
            valid = self._fallback_split(valid_config_nodes, latency_cap=latency_cap, test_url=test_url)

        print(f"  实测可用: {len(valid)}/{len(nodes)}")
        return valid

    def test_nodes_relay(
        self,
        nodes: List[Dict],
        relay_node: Dict,
        relay_self_latency: int = 0,
        concurrency: int = RELAY_CONCURRENCY,
        latency_cap: int = MAX_LATENCY,
    ) -> List[Dict]:
        """通过 China relay 测试 foreign 节点（Stage-2）"""
        if not nodes or relay_node is None:
            return []

        print(f"  relay-test {len(nodes)} nodes via relay (concurrency {concurrency})...")
        return self._test_batch(
            nodes,
            relay_node=relay_node,
            concurrency=concurrency,
            latency_offset=relay_self_latency,
            latency_cap=latency_cap,
        )

    def _validate_config(self, nodes: List[Dict]) -> List[Dict]:
        """用 mihomo -t 预校验配置，批量剔除致命节点"""
        current = list(nodes)
        total_dropped = 0

        while True:
            if not current:
                break

            config, _, proxy_node_indices = self._config_builder.build_test_config(current, 0)

            with tempfile.TemporaryDirectory(prefix="mihomo-validate-") as workdir:
                cfg_path = Path(workdir) / "config.yaml"
                self._config_builder.write_config(config, cfg_path)

                r = subprocess.run(
                    [str(self.binary), "-t", "-d", workdir, "-f", str(cfg_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    break

                # 收集所有报错的 proxy 位置，一次性批量剔除
                text = r.stdout or r.stderr or ""
                positions = [int(p) for p in re.findall(r"proxy (\d+):", text)]
                node_idxs = sorted(
                    {proxy_node_indices[p] for p in positions if 0 <= p < len(proxy_node_indices)},
                    reverse=True,
                )
                if not node_idxs:
                    break
                for idx in node_idxs:
                    if 0 <= idx < len(current):
                        current.pop(idx)
                        total_dropped += 1

        if total_dropped:
            print(f"  配置校验剔除: {total_dropped} 个致命节点")
        return current

    def _test_batch(
        self,
        nodes: List[Dict],
        relay_node: Optional[Dict] = None,
        concurrency: int = PROXY_TEST_CONCURRENCY,
        latency_offset: int = 0,
        latency_cap: int = MAX_LATENCY,
        test_url: str = MIHOMO_TEST_URL,
    ) -> List[Dict]:
        """单批测试：启动一个 mihomo 实例测全部节点"""
        if not nodes:
            return []

        port = _free_port()
        config, proxy_to_node, _ = self._config_builder.build_test_config(
            nodes, port, relay_node=relay_node,
        )
        if not proxy_to_node:
            return []

        with tempfile.TemporaryDirectory(prefix="mihomo-test-") as workdir:
            cfg_path = Path(workdir) / "config.yaml"
            self._config_builder.write_config(config, cfg_path)

            proc_mgr = ProcessManager(self.binary, workdir)
            proc_mgr.start(cfg_path)

            try:
                if not proc_mgr.wait_ready(port):
                    out = proc_mgr.get_startup_output()
                    raise RuntimeError(out)

                tester = LatencyTester(
                    port=port,
                    proxy_to_node=proxy_to_node,
                    concurrency=concurrency,
                    latency_offset=latency_offset,
                    latency_cap=latency_cap,
                    test_url=test_url,
                )
                return tester.run_tests()
            finally:
                proc_mgr.terminate()

    def _fallback_split(
        self,
        nodes: List[Dict],
        relay_node: Optional[Dict] = None,
        concurrency: int = PROXY_TEST_CONCURRENCY,
        latency_offset: int = 0,
        latency_cap: int = MAX_LATENCY,
        test_url: str = MIHOMO_TEST_URL,
    ) -> List[Dict]:
        """兜底：二分拆分重试定位问题节点"""
        BATCH_THRESHOLD = 1

        def _run(batch: List[Dict]) -> List[Dict]:
            if not batch:
                return []
            try:
                return self._test_batch(
                    batch,
                    relay_node=relay_node,
                    concurrency=concurrency,
                    latency_offset=latency_offset,
                    latency_cap=latency_cap,
                    test_url=test_url,
                )
            except RuntimeError:
                if len(batch) <= BATCH_THRESHOLD:
                    return []
                mid = len(batch) // 2
                return _run(batch[:mid]) + _run(batch[mid:])

        return _run(nodes)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# 保持向后兼容的函数接口
def ensure_binary() -> Path:
    manager = BinaryManager(MIHOMO_VERSION)
    return manager.ensure_binary()


def test_nodes(
    nodes: List[Dict],
    latency_cap: int = MAX_LATENCY,
    test_url: str = MIHOMO_TEST_URL,
) -> List[Dict]:
    tester = MihomoTester()
    return tester.test_nodes(nodes, latency_cap=latency_cap, test_url=test_url)


def test_nodes_relay(
    nodes: List[Dict],
    relay_node: Dict,
    relay_self_latency: int = 0,
    concurrency: int = RELAY_CONCURRENCY,
    latency_cap: int = MAX_LATENCY,
) -> List[Dict]:
    tester = MihomoTester()
    return tester.test_nodes_relay(
        nodes, relay_node,
        relay_self_latency=relay_self_latency,
        concurrency=concurrency,
        latency_cap=latency_cap,
    )
