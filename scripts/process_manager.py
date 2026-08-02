#!/usr/bin/env python3
"""
进程管理器 - 负责 mihomo 进程的启动、等待和清理
符合 SRP: 单一职责，只管理进程生命周期
"""

import subprocess
import time
import urllib.error
from pathlib import Path
from typing import Optional

from scripts.utils import get_local_opener


class ProcessManager:
    """管理 mihomo 进程的生命周期"""

    def __init__(self, binary: Path, workdir: str):
        self._binary = binary
        self._workdir = workdir
        self._proc: Optional[subprocess.Popen] = None

    def start(self, config_path: Path) -> None:
        """启动 mihomo 进程"""
        cmd = [str(self._binary), "-d", self._workdir, "-f", str(config_path)]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def wait_ready(self, port: int, timeout: float = 30.0) -> bool:
        """等待 mihomo API 就绪"""
        url = f"http://127.0.0.1:{port}/version"
        deadline = time.monotonic() + timeout
        opener = get_local_opener()
        while time.monotonic() < deadline:
            try:
                with opener.open(url, timeout=1) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.3)
        return False

    def get_startup_output(self, max_chars: int = 4000) -> str:
        """获取启动输出（用于错误诊断）。

        安全读取：先终止进程释放 pipe，再读取已缓冲的输出，避免 read() 阻塞死锁
        （wait_ready 超时但进程未死时，read 会无限阻塞直到 EOF）。"""
        if self._proc is None:
            return ""
        # 先终止进程，确保 stdout pipe 关闭，read 不会阻塞
        self._proc.terminate()
        try:
            self._proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            try:
                self._proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                pass
        if self._proc.stdout:
            try:
                data = self._proc.stdout.read(max_chars)
                return data or ""
            except (OSError, ValueError):
                pass
        return ""

    def terminate(self, kill_timeout: float = 3.0) -> None:
        """终止进程并回收，避免僵尸进程"""
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=kill_timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            try:
                self._proc.wait(timeout=kill_timeout)
            except subprocess.TimeoutExpired:
                pass

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
