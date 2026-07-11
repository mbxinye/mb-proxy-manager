#!/usr/bin/env python3

import json
import sys
import time
from collections import Counter
from pathlib import Path

from scripts.config import MAX_OUTPUT_NODES, MINI_OUTPUT_NODES
from scripts.fetcher import fetch_all
from scripts.output import write
from scripts.parser import parse_all
from scripts.tester import run as test_all


def run():
  start = time.time()

  subs_file = Path("subscriptions.txt")
  if not subs_file.exists():
    print("\u274c \u672a\u627e\u5230 subscriptions.txt")
    sys.exit(1)

  urls = []
  sub_priority: dict = {}
  for line in subs_file.read_text(encoding="utf-8").split("\n"):
    line = line.strip()
    if not line or line.startswith("#"):
      continue
    parts = line.split()
    url = parts[0]
    prio = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else 0
    urls.append(url)
    sub_priority[url] = prio
  print(f"\u8ba2\u9605\u6765\u6e90: {len(urls)} \u4e2a\u94fe\u63a5\n")

  # 1. Fetch
  print("=" * 50)
  print("\u4e0b\u8f7d\u8ba2\u9605...")
  fetched = fetch_all(urls)

  # 2. Parse
  print("\n\u89e3\u6790\u8282\u70b9...")
  all_nodes = parse_all(fetched)

  # 3. Dedup
  seen = set()
  unique = []
  for n in all_nodes:
    key = f"{n['server']}:{n['port']}:{n.get('type', '')}"
    if key not in seen:
      seen.add(key)
      unique.append(n)
  print(f"  \u53bb\u91cd\u540e: {len(unique)} \u4e2a\u552f\u4e00\u8282\u70b9\n")

  # 4. mihomo end-to-end test
  print("=" * 50)
  print("\u9a8c\u8bc1\u8282\u70b9...")
  valid = test_all(unique)

  # 注入订阅优先级到节点（复用 _sub_url 关联）
  for n in valid:
    n["_sub_priority"] = sub_priority.get(n.get("_sub_url", ""), 0)

  # Per-subscription stats: parsed / deduped / valid (with priority)
  parsed_by = Counter(n.get("_sub_url", "?") for n in all_nodes)
  dedup_by = Counter(n.get("_sub_url", "?") for n in unique)
  valid_by = Counter(n.get("_sub_url", "?") for n in valid)
  print("\n\u8ba2\u9605\u8282\u70b9\u7edf\u8ba1 (\u4f18\u5148\u7ea7 | \u89e3\u6790 / \u53bb\u91cd / \u53ef\u7528):")
  for url in urls:
    prio = sub_priority.get(url, 0)
    p, d, v = parsed_by.get(url, 0), dedup_by.get(url, 0), valid_by.get(url, 0)
    print(f"  [{prio:>3}] {url[:56]:58} {p:>4} / {d:>4} / {v:>4}")
  total_label = "\u6c47\u603b"
  print(f"  {'':5}{total_label:58} {len(all_nodes):>4} / {len(unique):>4} / {len(valid):>4}")

  # 5. Output (always writes files, even if empty)
  print("\n" + "=" * 50)
  print("\u751f\u6210\u914d\u7f6e...")
  write(valid, MAX_OUTPUT_NODES, MINI_OUTPUT_NODES)

  elapsed = time.time() - start
  print(f"\n\u2713 \u5b8c\u6210! \u8017\u65f6: {elapsed:.1f}\u79d2")
  print(f"  {len(all_nodes)} \u8282\u70b9 \u2192 {len(valid)} \u6709\u6548 \u2192 {min(len(valid), MAX_OUTPUT_NODES)} \u8f93\u51fa")
