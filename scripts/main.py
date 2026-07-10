#!/usr/bin/env python3

import json
import sys
import time
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

  urls = [
    line.strip()
    for line in subs_file.read_text(encoding="utf-8").split("\n")
    if line.strip() and not line.startswith("#")
  ]
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

  # 5. Output (always writes files, even if empty)
  print("\n" + "=" * 50)
  print("\u751f\u6210\u914d\u7f6e...")
  write(valid, MAX_OUTPUT_NODES, MINI_OUTPUT_NODES)

  elapsed = time.time() - start
  print(f"\n\u2713 \u5b8c\u6210! \u8017\u65f6: {elapsed:.1f}\u79d2")
  print(f"  {len(all_nodes)} \u8282\u70b9 \u2192 {len(valid)} \u6709\u6548 \u2192 {min(len(valid), MAX_OUTPUT_NODES)} \u8f93\u51fa")
