#!/usr/bin/env python3

import sys
import time
from collections import Counter
from pathlib import Path

from scripts.config import MAX_OUTPUT_NODES, MINI_OUTPUT_NODES
from scripts.dedup import dedup_nodes
from scripts.fetcher import fetch_all
from scripts.log import get_logger
from scripts.output import write
from scripts.parser import parse_all
from scripts.tester import run as test_all

log = get_logger("main")


def _load_subscriptions(path: Path):
  """加载订阅源列表，返回 (urls, sub_priority)"""
  if not path.exists():
    log.error(f"❌ 未找到 {path.name}")
    sys.exit(1)
  urls = []
  sub_priority: dict = {}
  for line in path.read_text(encoding="utf-8").split("\n"):
    line = line.strip()
    if not line or line.startswith("#"):
      continue
    parts = line.split()
    url = parts[0]
    prio = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else 0
    urls.append(url)
    sub_priority[url] = prio
  return urls, sub_priority


def run():
  start = time.time()

  try:
    urls, sub_priority = _load_subscriptions(Path("subscriptions.txt"))
    log.info(f"订阅来源: {len(urls)} 个链接\n")

    # 1. Fetch
    log.info("=" * 50)
    log.info("下载订阅...")
    fetched = fetch_all(urls)

    # 2. Parse
    log.info("\n解析节点...")
    all_nodes = parse_all(fetched)

    # 3. Dedup
    unique = dedup_nodes(all_nodes)
    log.info(f"  去重后: {len(unique)} 个唯一节点\n")

    # 4. mihomo end-to-end test
    log.info("=" * 50)
    log.info("验证节点...")
    valid = test_all(unique)

    # 注入订阅优先级到节点（复用 _sub_url 关联）
    for n in valid:
      n["_sub_priority"] = sub_priority.get(n.get("_sub_url", ""), 0)

    # Per-subscription stats: parsed / deduped / valid (with priority)
    parsed_by = Counter(n.get("_sub_url", "?") for n in all_nodes)
    dedup_by = Counter(n.get("_sub_url", "?") for n in unique)
    valid_by = Counter(n.get("_sub_url", "?") for n in valid)
    log.info("\n订阅节点统计 (优先级 | 解析 / 去重 / 可用):")
    for url in urls:
      prio = sub_priority.get(url, 0)
      p, d, v = parsed_by.get(url, 0), dedup_by.get(url, 0), valid_by.get(url, 0)
      log.info(f"  [{prio:>3}] {url[:56]:58} {p:>4} / {d:>4} / {v:>4}")
    total_label = "汇总"
    log.info(f"  {'':5}{total_label:58} {len(all_nodes):>4} / {len(unique):>4} / {len(valid):>4}")

    # 5. Output (always writes files, even if empty)
    log.info("\n" + "=" * 50)
    log.info("生成配置...")
    write(valid, MAX_OUTPUT_NODES, MINI_OUTPUT_NODES)

    elapsed = time.time() - start
    log.info(f"\n✓ 完成! 耗时: {elapsed:.1f}秒")
    log.info(f"  {len(all_nodes)} 节点 → {len(valid)} 有效 → {min(len(valid), MAX_OUTPUT_NODES)} 输出")
  except Exception as e:
    log.exception(f"\n❌ 重大错误: {e}")
    sys.exit(1)
