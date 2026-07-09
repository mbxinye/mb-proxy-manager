#!/usr/bin/env python3

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from scripts.config import TCP_TIMEOUT, BATCH_SIZE, MAX_LATENCY


def _test_one(node: Dict) -> Tuple[bool, int]:
  host = node.get("server", "")
  port = node.get("port", 0)
  if not host or not port:
    return False, 9999
  try:
    ip = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TCP_TIMEOUT)
    start = time.time()
    sock.connect((ip, port))
    latency = int((time.time() - start) * 1000)
    sock.close()
    return True, latency
  except Exception:
    return False, 9999


def run(nodes: List[Dict]) -> List[Dict]:
  total = len(nodes)
  print(f"  \u6b63\u5728\u6d4b\u8bd5 {total} \u4e2a\u8282\u70b9 (TCP\u5e76\u53d1 {BATCH_SIZE})...")

  valid: List[Dict] = []
  with ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
    futures = {pool.submit(_test_one, n): n for n in nodes}
    for f in as_completed(futures):
      node = futures[f]
      success, latency = f.result()
      if success and latency <= MAX_LATENCY:
        node["latency"] = latency
        valid.append(node)

  valid.sort(key=lambda x: x["latency"])
  print(f"  TCP\u901a\u8fc7: {len(valid)}/{total}")
  return valid
