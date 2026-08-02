#!/usr/bin/env python3
"""
Mihomo 二进制管理器 - 负责下载和解压 mihomo 内核
符合 SRP: 单一职责，只管理二进制生命周期
"""

import gzip
import os
import platform
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Tuple

from scripts.log import get_logger

BIN_DIR = Path("bin")
DOWNLOAD_BASE = "https://github.com/MetaCubeX/mihomo/releases/download"

log = get_logger("mihomo_manager")


def _platform_asset(ver: str) -> Tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64-v3"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = machine
    if system in ("linux", "darwin"):
        return f"mihomo-{system}-{arch}-{ver}.gz", "gz"
    if system == "windows":
        return f"mihomo-windows-{arch}-{ver}.zip", "zip"
    raise RuntimeError(f"unsupported platform: {system}/{machine}")


class BinaryManager:
    """管理 mihomo 二进制的下载和缓存"""

    def __init__(self, version: str):
        self._version = version
        self._exe_name = "mihomo.exe" if os.name == "nt" else "mihomo"

    @property
    def version(self) -> str:
        return self._version

    def ensure_binary(self) -> Path:
        """确保 mihomo 二进制存在，不存在则下载"""
        target = BIN_DIR / self._exe_name
        if target.exists():
            return target

        BIN_DIR.mkdir(parents=True, exist_ok=True)
        asset, kind = _platform_asset(self._version)
        url = f"{DOWNLOAD_BASE}/{self._version}/{asset}"
        log.info(f"  下载 mihomo 内核 {self._version}: {url}")

        tmp_archive = BIN_DIR / asset
        _download(url, tmp_archive)
        _extract_binary(tmp_archive, target, kind)
        tmp_archive.unlink(missing_ok=True)
        log.info(f"  ✓ mihomo 就绪: {target}")
        return target


def _download(url: str, dest: Path, timeout: int = 180):
    from urllib.request import Request, urlopen
    req = Request(url, headers={"User-Agent": "mb-proxy-manager"})
    with urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"下载失败: HTTP {resp.status}")
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)


def _extract_binary(archive: Path, target: Path, kind: str):
    if kind == "zip":
        with zipfile.ZipFile(archive) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            member = next(
                (n for n in names if n.lower().endswith(("mihomo.exe", "mihomo"))),
                names[0],
            )
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
    else:
        try:
            with tarfile.open(archive, "r:gz") as tf:
                members = [m for m in tf.getmembers() if m.isfile()]
                bin_member = next(
                    (m for m in members if os.path.basename(m.name).lower().endswith("mihomo")),
                    members[0],
                )
                src = tf.extractfile(bin_member)
                with open(target, "wb") as dst:
                    dst.write(src.read())
        except tarfile.ReadError:
            with gzip.open(archive, "rb") as gz, open(target, "wb") as dst:
                dst.write(gz.read())
    if os.name != "nt":
        mode = os.stat(target).st_mode
        os.chmod(target, mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
