#!/usr/bin/env python3

import html
import re
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


_SOURCES = {
  "freevpnnode": _source_freevpnnode,
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
  return nodes
