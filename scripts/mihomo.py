#!/usr/bin/env python3

import gzip
import json
import os
import platform
import re
import socket
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import yaml

from scripts.config import (
  MAX_LATENCY,
  MIHOMO_TEST_TIMEOUT,
  MIHOMO_TEST_URL,
  MIHOMO_VERSION,
  PROXY_TEST_CONCURRENCY,
)
from scripts.output import _to_clash_node

BIN_DIR = Path("bin")
DOWNLOAD_BASE = "https://github.com/MetaCubeX/mihomo/releases/download"

# 访问本地 mihomo API 必须绕过系统代理 env（HTTP_PROXY 会把 127.0.0.1 也走代理）
_LOCAL_OPENER = build_opener(ProxyHandler({}))


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


def _download(url: str, dest: Path, timeout: int = 180):
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
    # 版本化 .gz 可能是单文件 gzip 二进制，也可能是 tar.gz；先按 tar 试，失败则按单 gzip。
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


def ensure_binary() -> Path:
  exe_name = "mihomo.exe" if os.name == "nt" else "mihomo"
  target = BIN_DIR / exe_name
  if target.exists():
    return target
  BIN_DIR.mkdir(parents=True, exist_ok=True)
  asset, kind = _platform_asset(MIHOMO_VERSION)
  url = f"{DOWNLOAD_BASE}/{MIHOMO_VERSION}/{asset}"
  print(f"  下载 mihomo 内核 {MIHOMO_VERSION}: {url}")
  tmp_archive = BIN_DIR / asset
  _download(url, tmp_archive)
  _extract_binary(tmp_archive, target, kind)
  tmp_archive.unlink(missing_ok=True)
  print(f"  \u2713 mihomo 就绪: {target}")
  return target


def _free_port() -> int:
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("127.0.0.1", 0))
    return s.getsockname()[1]


def _build_test_config(
  nodes: List[Dict], port: int
) -> Tuple[Dict, Dict[str, Dict]]:
  clash_proxies: List[Dict] = []
  proxy_to_node: Dict[str, Dict] = {}
  for i, n in enumerate(nodes):
    synthetic = dict(n)
    synthetic["name"] = f"node-{i}"
    try:
      clash_proxies.append(_to_clash_node(synthetic))
      proxy_to_node[f"node-{i}"] = n
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
  return config, proxy_to_node


def _wait_ready(port: int, timeout: float = 30.0) -> bool:
  url = f"http://127.0.0.1:{port}/version"
  deadline = time.monotonic() + timeout
  while time.monotonic() < deadline:
    try:
      with _LOCAL_OPENER.open(url, timeout=1) as resp:
        if resp.status == 200:
          return True
    except Exception:
      time.sleep(0.3)
  return False


def _test_one(base: str, name: str) -> Optional[int]:
  url = (
    f"{base}/{quote(name, safe='')}/delay"
    f"?timeout={MIHOMO_TEST_TIMEOUT}&url={quote(MIHOMO_TEST_URL, safe='')}"
  )
  http_timeout = MIHOMO_TEST_TIMEOUT / 1000 + 3
  try:
    with _LOCAL_OPENER.open(url, timeout=http_timeout) as resp:
      if resp.status != 200:
        return None
      data = json.loads(resp.read().decode("utf-8"))
      delay = data.get("delay")
      return int(delay) if delay is not None else None
  except Exception:
    return None


def _run_delay_tests(
  port: int, proxy_to_node: Dict[str, Dict]
) -> List[Dict]:
  base = f"http://127.0.0.1:{port}/proxies"
  results: List[Dict] = []
  total = len(proxy_to_node)
  latency_dropped = 0
  with ThreadPoolExecutor(max_workers=PROXY_TEST_CONCURRENCY) as pool:
    futures = {pool.submit(_test_one, base, name): name for name in proxy_to_node}
    done = 0
    for f in as_completed(futures):
      done += 1
      name = futures[f]
      latency = f.result()
      if latency is not None:
        node = proxy_to_node[name]
        node["latency"] = latency
        if MAX_LATENCY > 0 and latency > MAX_LATENCY:
          latency_dropped += 1
        else:
          results.append(node)
      if done % 50 == 0 or done == total:
        print(f"    进度 {done}/{total}, 可用 {len(results)}")
  if latency_dropped:
    print(f"    延迟超阈值(>{MAX_LATENCY}ms)剔除: {latency_dropped}")
  return results


def _validate_config(binary: Path, nodes: List[Dict]) -> List[Dict]:
  """用 mihomo -t 预校验配置，循环剔除致命节点，保证返回的节点列表 0 fatal。"""
  current = list(nodes)
  total_dropped = 0
  while True:
    if not current:
      break
    config, _ = _build_test_config(current, 0)
    with tempfile.TemporaryDirectory(prefix="mihomo-validate-") as workdir:
      cfg_path = Path(workdir) / "config.yaml"
      with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False, indent=2)
      r = subprocess.run(
        [str(binary), "-t", "-d", workdir, "-f", str(cfg_path)],
        capture_output=True, text=True, timeout=30,
      )
      if r.returncode == 0:
        break
      # 解析 "proxy N: ..." 提取错误节点索引（N 对应 proxies 列表位置，从 0 起）
      m = re.search(r"proxy (\d+):", r.stdout or r.stderr or "")
      if not m:
        # 无法定位错误，放弃校验直接返回当前列表（交给兜底处理）
        break
      idx = int(m.group(1))
      if idx >= len(current):
        break
      current.pop(idx)
      total_dropped += 1
  if total_dropped:
    print(f"  配置校验剔除: {total_dropped} 个致命节点")
  return current


def _test_batch(binary: Path, nodes: List[Dict]) -> List[Dict]:
  """单批测试：启动一个 mihomo 实例测全部节点。启动失败抛 RuntimeError。"""
  if not nodes:
    return []
  port = _free_port()
  config, proxy_to_node = _build_test_config(nodes, port)
  if not proxy_to_node:
    return []

  with tempfile.TemporaryDirectory(prefix="mihomo-test-") as workdir:
    cfg_path = Path(workdir) / "config.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
      yaml.dump(config, f, allow_unicode=True, sort_keys=False, indent=2)

    cmd = [str(binary), "-d", workdir, "-f", str(cfg_path)]
    proc = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      text=True,
    )
    try:
      if not _wait_ready(port):
        out = ""
        if proc.stdout:
          try:
            out = proc.stdout.read(4000)
          except Exception:
            pass
        raise RuntimeError(out)
      return _run_delay_tests(port, proxy_to_node)
    finally:
      proc.terminate()
      try:
        proc.wait(timeout=3)
      except subprocess.TimeoutExpired:
        proc.kill()


def _fallback_split(binary: Path, nodes: List[Dict]) -> List[Dict]:
  """兜底：-t 漏报导致单批 fatal 时，二分拆分重试定位问题节点。"""
  BATCH_THRESHOLD = 1

  def _run(batch: List[Dict]) -> List[Dict]:
    if not batch:
      return []
    try:
      return _test_batch(binary, batch)
    except RuntimeError:
      if len(batch) <= BATCH_THRESHOLD:
        return []
      mid = len(batch) // 2
      return _run(batch[:mid]) + _run(batch[mid:])

  return _run(nodes)


def test_nodes(nodes: List[Dict]) -> List[Dict]:
  if not nodes:
    return []
  binary = ensure_binary()

  print(f"  \u771f\u5b9e\u6d4b\u8bd5 {len(nodes)} \u4e2a\u8282\u70b9 "
        f"(\u5e76\u53d1 {PROXY_TEST_CONCURRENCY})...")

  # 预校验：剔除会让 mihomo fatal 的节点，保证单批 0 fatal
  valid_config_nodes = _validate_config(binary, nodes)
  if not valid_config_nodes:
    print("  \u65e0\u914d\u7f6e\u5408\u6cd5\u8282\u70b9")
    return []

  # 单批跑完，不再二分降级
  try:
    valid = _test_batch(binary, valid_config_nodes)
  except RuntimeError as e:
    # 兜底：-t 漏报导致仍 fatal，退回二分（极少触发）
    print(f"  \u26a0 \u5355\u6279\u542f\u52a8\u5931\u8d25\uff0c\u9000\u56de\u5206\u6279: {str(e)[:100]}")
    valid = _fallback_split(binary, valid_config_nodes)

  print(f"  \u5b9e\u6d4b\u53ef\u7528: {len(valid)}/{len(nodes)}")
  return valid
