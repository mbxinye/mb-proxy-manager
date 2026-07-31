#!/usr/bin/env python3

import socket
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import List

from scripts.config import SUBSCRIPTION_TIMEOUT

USER_AGENT = (
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
  "AppleWebKit/537.36 (KHTML, like Gecko) "
  "Chrome/131.0.0.0 Safari/537.36"
)

# 单次重试即可；urllib timeout 不覆盖 Windows DNS 解析，加 socket 级兜底
_MAX_RETRIES = 0


def _fetch_one(url: str) -> dict:
  for attempt in range(_MAX_RETRIES + 1):
    try:
      # socket.setdefaulttimeout 覆盖 DNS 解析阶段（urllib timeout 不保证覆盖）
      socket.setdefaulttimeout(SUBSCRIPTION_TIMEOUT)
      ctx = ssl.create_default_context()
      req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
      with urllib.request.urlopen(req, timeout=SUBSCRIPTION_TIMEOUT, context=ctx) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        return {"url": url, "content": content, "success": True}
    except Exception as e:
      if attempt < _MAX_RETRIES:
        continue
      return {"url": url, "content": None, "error": str(e)[:60], "success": False}


def fetch_all(urls: List[str]) -> List[dict]:
  total = len(urls)
  print(f"  \u4e0b\u8f7d {total} \u4e2a\u8ba2\u9605...")
  results = []
  pool = ThreadPoolExecutor(max_workers=min(total, 20))
  future_to_url = {pool.submit(_fetch_one, u): u for u in urls}
  remaining = set(future_to_url.keys())
  try:
    for f in as_completed(future_to_url, timeout=SUBSCRIPTION_TIMEOUT + 15):
      remaining.discard(f)
      r = f.result()
      results.append(r)
      status = "\u2713" if r["success"] else "\u2717"
      print(f"    {status} {r['url'][:60]}..." if r["success"] else f"    {status} {r['url'][:60]}... ({r.get('error', '')})")
  except FuturesTimeoutError:
    # \u5269\u4f59\u4efb\u52a1\u8d85\u65f6\u672a\u5b8c\u6210 \u2192 \u53d6\u6d88\u5e76\u6807\u8bb0\u5931\u8d25
    for f in remaining:
      f.cancel()
      url = future_to_url[f]
      error_msg = "\u8fde\u63a5\u8d85\u65f6\uff08\u5df2\u53d6\u6d88\uff09"
      print(f"    \u2717 {url[:60]}... ({error_msg})")
      results.append({"url": url, "content": None, "error": error_msg, "success": False})
  finally:
    # \u4e0d\u7b49\u5f85\u5361\u6b7b\u7684\u7ebf\u7a0b\uff0c\u5b83\u4eec\u5728\u8fdb\u7a0b\u9000\u51fa\u65f6\u4f1a\u88ab\u6e05\u7406
    pool.shutdown(wait=False)
  ok = sum(1 for r in results if r["success"])
  print(f"  \u4e0b\u8f7d\u5b8c\u6210: {ok}/{total} \u6210\u529f")
  return results
