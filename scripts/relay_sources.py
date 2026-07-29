#!/usr/bin/env python3

import html
import json
import re
import socket
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from scripts.config import (
  RELAY_EXTERNAL_PAGES,
  RELAY_EXTERNAL_PROTOCOLS,
  RELAY_EXTERNAL_SOURCES,
  SUBSCRIPTION_TIMEOUT,
)

USER_AGENT = (
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
  "AppleWebKit/537.36 (KHTML, like Gecko) "
  "Chrome/131.0.0.0 Safari/537.36"
)

_FREEVPNNODE_BASE = "https://cn.freevpnnode.com/free-proxy-for-china/"

_TAG_RE = re.compile(r"<[^>]+>")
_DATA_TEXT_RE = re.compile(r'data-text="([^"]*)"')
# 12 columns: IP, Port, Username, Password, Country, Protocol, Anonymity,
# Speed, Uptime, Response, Latency, Updated
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)


def _strip_tags(s: str) -> str:
  return html.unescape(_TAG_RE.sub("", s or "")).strip()


def _credential(cell: str) -> str:
  # Site hides user/pass behind a js toggle; the real value (or 'no need')
  # lives in the img data-text attribute.
  m = _DATA_TEXT_RE.search(cell or "")
  if not m:
    return ""
  v = m.group(1)
  return "" if v.lower() == "no need" else v


def _tcp_reachable(server: str, port: int, timeout: float = 3.0) -> bool:
  # 免费代理存活时间在分钟级，抓取到 mihomo 测试之间有延迟。
  # TCP 预过滤（socket 3s）先剔除端口关闭/主机不可达的代理，
  # 避免把 33 个死代理全塞进 mihomo（启动 + delay test 耗时约 30s）。
  try:
    with socket.create_connection((server, port), timeout=timeout):
      return True
  except (OSError, socket.timeout):
    return False


def _tcp_prefilter(nodes: List[Dict], timeout: float = 3.0) -> List[Dict]:
  if not nodes:
    return []
  with ThreadPoolExecutor(max_workers=min(len(nodes), 20)) as pool:
    futures = {
      pool.submit(_tcp_reachable, n["server"], n["port"], timeout): n
      for n in nodes
    }
    reachable = [futures[f] for f in as_completed(futures) if f.result()]
  return reachable


def _fetch(url: str) -> Optional[str]:
  try:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=SUBSCRIPTION_TIMEOUT, context=ctx) as resp:
      return resp.read().decode("utf-8", errors="ignore")
  except Exception as e:
    print(f"    x {url[:70]} ({str(e)[:60]})")
    return None


def _parse_freevpnnode_page(content: str) -> List[Dict]:
  nodes: List[Dict] = []
  s = content.find("<tbody>")
  e = content.find("</tbody>", s)
  if s < 0 or e < 0:
    return nodes
  tbody = content[s:e]
  allowed = set(RELAY_EXTERNAL_PROTOCOLS)
  for row in _ROW_RE.findall(tbody):
    cells = _CELL_RE.findall(row)
    if len(cells) < 6:
      continue
    ip = _strip_tags(cells[0])
    port = _strip_tags(cells[1])
    proto = _strip_tags(cells[5]).lower()
    if not ip or not port or proto not in allowed:
      continue
    if not re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", ip):
      continue
    try:
      port_i = int(port)
    except ValueError:
      continue
    user = _credential(cells[2])
    pwd = _credential(cells[3])
    node: Dict = {
      "type": proto,
      "name": f"CN-RELAY-{proto}-{ip}:{port_i}",
      "server": ip,
      "port": port_i,
      "_external_relay": True,
    }
    if user:
      node["username"] = user
    if pwd:
      node["password"] = pwd
    nodes.append(node)
  return nodes


def _source_freevpnnode() -> List[Dict]:
  pages = max(1, RELAY_EXTERNAL_PAGES)
  urls = [_FREEVPNNODE_BASE] + [
    f"{_FREEVPNNODE_BASE}?page={p}" for p in range(2, pages + 1)
  ]
  print(f"  [external relay] freevpnnode {len(urls)} pages")
  nodes: List[Dict] = []
  with ThreadPoolExecutor(max_workers=min(len(urls), 6)) as pool:
    futures = {pool.submit(_fetch, u): u for u in urls}
    for f in as_completed(futures):
      content = f.result()
      if content:
        nodes.extend(_parse_freevpnnode_page(content))
  return nodes


_PROXYSCRAPE_URL = (
  "https://api.proxyscrape.com/v4/free-proxy-list/get"
  "?request=display_free_proxies&proxy_format=protocolipport"
  "&format=json&country=CN&timeout=10000"
)


def _source_proxyscrape() -> List[Dict]:
  # proxyscrape API 返回 JSON，含中国代理列表（从 US runner 可访问）
  print("  [external relay] proxyscrape")
  content = _fetch(_PROXYSCRAPE_URL)
  if not content:
    return []
  try:
    data = json.loads(content)
  except (json.JSONDecodeError, ValueError):
    return []
  proxies = data.get("proxies", []) if isinstance(data, dict) else []
  allowed = set(RELAY_EXTERNAL_PROTOCOLS)
  nodes: List[Dict] = []
  for p in proxies:
    proto = (p.get("protocol") or "").lower()
    ip = p.get("ip") or p.get("server") or ""
    port = p.get("port")
    if not ip or not port or proto not in allowed:
      continue
    try:
      port_i = int(port)
    except (ValueError, TypeError):
      continue
    node: Dict = {
      "type": proto,
      "name": f"CN-RELAY-PS-{ip}:{port_i}",
      "server": ip,
      "port": port_i,
      "_external_relay": True,
    }
    user = p.get("username")
    pwd = p.get("password")
    if user:
      node["username"] = user
    if pwd:
      node["password"] = pwd
    nodes.append(node)
  return nodes


_SOURCES = {
  "freevpnnode": _source_freevpnnode,
  "proxyscrape": _source_proxyscrape,
}


def fetch_external_relays() -> List[Dict]:
  # Fetch candidate mainland-China relays from configured external sources.
  # Returns deduped http/socks5 node dicts; reachability is verified later by
  # a stage-1 mihomo test (in tester.run). On any source failure, logs and
  # returns whatever was collected.
  if not RELAY_EXTERNAL_SOURCES:
    return []
  raw: List[Dict] = []
  for key in RELAY_EXTERNAL_SOURCES:
    fn = _SOURCES.get(key.lower())
    if fn is None:
      print(f"  [external relay] unknown source '{key}', skipping")
      continue
    try:
      raw.extend(fn())
    except Exception as e:
      print(f"  [external relay] {key} failed: {str(e)[:100]}")

  seen = set()
  nodes: List[Dict] = []
  for n in raw:
    k = (n["type"], n["server"], n["port"])
    if k in seen:
      continue
    seen.add(k)
    nodes.append(n)
  print(f"  [external relay] collected {len(nodes)} unique CN relays")

  # TCP 预过滤：免费代理存活率在分钟级，抓取时活的到 mihomo 测试可能已死。
  # 用 socket 3s 并发测 TCP 连通性，先剔除端口关闭/主机不可达的代理，
  # 避免把死代理全塞进 mihomo（启动 + delay test 耗时约 30s）。
  if nodes:
    before = len(nodes)
    nodes = _tcp_prefilter(nodes)
    print(f"  [external relay] TCP prefilter: {before} -> {len(nodes)} reachable")
  return nodes
