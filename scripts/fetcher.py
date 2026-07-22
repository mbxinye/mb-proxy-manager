#!/usr/bin/env python3

import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from scripts.config import SUBSCRIPTION_TIMEOUT

USER_AGENT = (
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
  "AppleWebKit/537.36 (KHTML, like Gecko) "
  "Chrome/131.0.0.0 Safari/537.36"
)


def _fetch_one(url: str) -> dict:
  try:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=SUBSCRIPTION_TIMEOUT, context=ctx) as resp:
      content = resp.read().decode("utf-8", errors="ignore")
      return {"url": url, "content": content, "success": True}
  except Exception as e:
    return {"url": url, "content": None, "error": str(e)[:60], "success": False}


def fetch_all(urls: List[str]) -> List[dict]:
  total = len(urls)
  print(f"  \u4e0b\u8f7d {total} \u4e2a\u8ba2\u9605...")
  results = []
  with ThreadPoolExecutor(max_workers=min(total, 20)) as pool:
    futures = {pool.submit(_fetch_one, u): u for u in urls}
    for f in as_completed(futures):
      r = f.result()
      results.append(r)
      status = "\u2713" if r["success"] else "\u2717"
      print(f"    {status} {r['url'][:60]}..." if r["success"] else f"    {status} {r['url'][:60]}... ({r.get('error', '')})")
  ok = sum(1 for r in results if r["success"])
  print(f"  \u4e0b\u8f7d\u5b8c\u6210: {ok}/{total} \u6210\u529f")
  return results
