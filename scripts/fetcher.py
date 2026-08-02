#!/usr/bin/env python3
"""订阅下载器 - SRP：只负责并发抓取订阅文本。

修复：删除 socket.setdefaulttimeout 全局副作用（改用 per-call timeout）；
异常收窄为网络类具体异常；print 改 logging。"""

import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import List

from scripts.config import SUBSCRIPTION_TIMEOUT
from scripts.log import get_logger

log = get_logger("fetcher")

USER_AGENT = (
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
  "AppleWebKit/537.36 (KHTML, like Gecko) "
  "Chrome/131.0.0.0 Safari/537.36"
)

MAX_RETRIES = 2
RETRY_BACKOFF = 2.0  # 指数退避基数（秒）


def _fetch_one(url: str) -> dict:
  # 仅捕获网络/SSL 类异常，编程错误（TypeError 等）向上抛出便于定位
  ctx = ssl.create_default_context()
  last_err = ""
  for attempt in range(MAX_RETRIES + 1):
    try:
      req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
      with urllib.request.urlopen(req, timeout=SUBSCRIPTION_TIMEOUT, context=ctx) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        return {"url": url, "content": content, "success": True}
    except (urllib.error.URLError, urllib.error.HTTPError, ssl.SSLError, TimeoutError, OSError) as e:
      last_err = str(e)[:60]
      # 5xx 与超时可重试；4xx（如 404/403）不重试
      if isinstance(e, urllib.error.HTTPError) and e.code and 400 <= e.code < 500:
        break
      if attempt < MAX_RETRIES:
        time.sleep(RETRY_BACKOFF * (attempt + 1))
  return {"url": url, "content": None, "error": last_err, "success": False}


def fetch_all(urls: List[str]) -> List[dict]:
  total = len(urls)
  log.info(f"  下载 {total} 个订阅...")
  results = []
  pool = ThreadPoolExecutor(max_workers=min(total, 20))
  future_to_url = {pool.submit(_fetch_one, u): u for u in urls}
  remaining = set(future_to_url.keys())
  try:
    for f in as_completed(future_to_url, timeout=SUBSCRIPTION_TIMEOUT + 15):
      remaining.discard(f)
      r = f.result()
      results.append(r)
      status = "✓" if r["success"] else "✗"
      if r["success"]:
        log.info(f"    {status} {r['url'][:60]}...")
      else:
        log.info(f"    {status} {r['url'][:60]}... ({r.get('error', '')})")
  except FuturesTimeoutError:
    # 剩余任务超时未完成 → 取消并标记失败
    for f in remaining:
      f.cancel()
      url = future_to_url[f]
      error_msg = "连接超时（已取消）"
      log.info(f"    ✗ {url[:60]}... ({error_msg})")
      results.append({"url": url, "content": None, "error": error_msg, "success": False})
  finally:
    # 不等待卡死的线程，它们在进程退出时会被清理
    pool.shutdown(wait=False)
  ok = sum(1 for r in results if r["success"])
  log.info(f"  下载完成: {ok}/{total} 成功")
  return results
