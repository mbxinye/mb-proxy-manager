#!/usr/bin/env python3

import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Iterable, Optional

from scripts.config import (
  GEOIP_DB_PATH,
  GEOIP_DB_URL,
  GEOIP_DNS_WORKERS,
  GEOIP_MAX_AGE_DAYS,
)

_reader = None
_reader_failed = False
_dns_cache: Dict[str, Optional[str]] = {}
_country_cache: Dict[str, Optional[str]] = {}


def ensure_geoip_db() -> Optional[Path]:
  path = Path(GEOIP_DB_PATH)
  if path.exists():
    age_days = (time.time() - path.stat().st_mtime) / 86400
    if age_days < GEOIP_MAX_AGE_DAYS:
      return path
  path.parent.mkdir(parents=True, exist_ok=True)
  print(f"  \u4e0b\u8f7d GeoIP \u6570\u636e\u5e93: {GEOIP_DB_URL}")
  try:
    req = urllib.request.Request(GEOIP_DB_URL, headers={"User-Agent": "mb-proxy-manager"})
    tmp = path.with_suffix(".tmp")
    with urllib.request.urlopen(req, timeout=120) as resp:
      with open(tmp, "wb") as f:
        while True:
          chunk = resp.read(65536)
          if not chunk:
            break
          f.write(chunk)
    tmp.replace(path)
    print(f"  \u2713 GeoIP \u5c31\u7eea: {path} ({path.stat().st_size // 1024} KB)")
    return path
  except Exception as e:
    print(f"  \u26a0 GeoIP \u4e0b\u8f7d\u5931\u8d25: {str(e)[:100]}")
    if path.exists():
      return path
    return None


def _get_reader():
  global _reader, _reader_failed
  if _reader is not None:
    return _reader
  if _reader_failed:
    return None
  try:
    import maxminddb
    path = ensure_geoip_db()
    if not path or not path.exists():
      _reader_failed = True
      return None
    _reader = maxminddb.open_database(str(path))
    return _reader
  except Exception as e:
    print(f"  \u26a0 GeoIP \u52a0\u8f7d\u5931\u8d25: {str(e)[:100]}")
    _reader_failed = True
    return None


def _resolve_ip(server: str) -> Optional[str]:
  if not server:
    return None
  if server in _dns_cache:
    return _dns_cache[server]
  ip = None
  try:
    socket.inet_aton(server)
    ip = server
  except OSError:
    try:
      infos = socket.getaddrinfo(server, None, socket.AF_INET)
      if infos:
        ip = infos[0][4][0]
    except Exception:
      ip = None
  _dns_cache[server] = ip
  return ip


def server_country(server: str) -> Optional[str]:
  if not server:
    return None
  if server in _country_cache:
    return _country_cache[server]
  ip = _resolve_ip(server)
  code = None
  if ip:
    reader = _get_reader()
    if reader:
      try:
        rec = reader.get(ip)
        if rec and isinstance(rec, dict):
          country = rec.get("country")
          if country:
            code = country.get("iso_code")
      except Exception:
        code = None
  _country_cache[server] = code
  return code


def prefetch_countries(servers: Iterable[str]) -> None:
  uniq = [s for s in dict.fromkeys(servers) if s]
  if not uniq:
    return
  _get_reader()
  if _reader_failed:
    return
  with ThreadPoolExecutor(max_workers=GEOIP_DNS_WORKERS) as pool:
    list(pool.map(server_country, uniq))
  print(f"  GeoIP \u9884\u53d6 {len(uniq)} \u4e2a\u4e3b\u673a")
