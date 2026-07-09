#!/usr/bin/env python3

import base64
import hashlib
import os
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from scripts.config import TCP_TIMEOUT, BATCH_SIZE, MAX_LATENCY


def _ws_upgrade(sock: socket.socket, host: str, path: str, timeout: float) -> bool:
  try:
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
      f"GET {path} HTTP/1.1\r\n"
      f"Host: {host}\r\n"
      f"Upgrade: websocket\r\n"
      f"Connection: Upgrade\r\n"
      f"Sec-WebSocket-Key: {key}\r\n"
      f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.settimeout(timeout)
    sock.sendall(req.encode())
    resp = sock.recv(1024)
    return b"101" in resp[:20]
  except Exception:
    return False


def _trojan_probe(sock: socket.socket, password: str, timeout: float) -> bool:
  try:
    r = hashlib.sha224(password.encode()).hexdigest()
    sock.settimeout(timeout)
    sock.sendall((r + "\r\n").encode())
    # CONNECT 1.1.1.1:80 (command + atyp + addr + port)
    sock.sendall(bytes([1, 0, 1, 1, 1, 1, 0, 80]))
    sock.recv(1)
    return True
  except Exception:
    return False


def _vless_probe(sock: socket.socket, uuid: str, timeout: float) -> bool:
  try:
    uid = uuid.replace("-", "")[:32]
    uid_bytes = bytes.fromhex(uid.ljust(32, "0"))
    # auth header: version(0x00) + UUID + security(0x00)
    auth = b"\x00" + uid_bytes + b"\x00"
    # TCP CONNECT 1.1.1.1:80
    req = auth + b"\x01\x00\x01\x01\x01\x01\x00\x50"
    sock.settimeout(timeout)
    sock.sendall(req)
    # 0x00 = success, 0x01 = invalid, timeout = no response (might be valid)
    try:
      resp = sock.recv(1)
      return resp == b"\x00"
    except socket.timeout:
      return True  # connection alive = likely valid
  except Exception:
    return False


def _http_probe(sock: socket.socket, timeout: float) -> bool:
  try:
    req = b"CONNECT 1.1.1.1:80 HTTP/1.1\r\nHost: 1.1.1.1\r\n\r\n"
    sock.settimeout(timeout)
    sock.sendall(req)
    resp = sock.recv(12)
    return resp[:12] == b"HTTP/1.1 200"
  except Exception:
    return False


def _test_one(node: Dict) -> Tuple[bool, int]:
  host = node.get("server", "")
  port = node.get("port", 0)
  if not host or not port:
    return False, 9999

  start = time.monotonic()
  sock = None

  try:
    ip = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TCP_TIMEOUT)
    sock.connect((ip, port))

    # TLS handshake
    if node.get("tls"):
      sni = node.get("servername") or node.get("sni") or host
      ctx = ssl._create_unverified_context()
      ctx.check_hostname = False
      ctx.verify_mode = ssl.CERT_NONE
      sock = ctx.wrap_socket(sock, server_hostname=sni)

    # WebSocket upgrade
    ptype = node.get("type", "").lower()
    network = node.get("network", "")
    if network in ("ws", "websocket"):
      ws_opts = node.get("ws-opts") or {}
      ws_host = ws_opts.get("headers", {}).get("Host", host)
      ws_path = ws_opts.get("path", "/")
      if not _ws_upgrade(sock, ws_host, ws_path, TCP_TIMEOUT):
        return False, int((time.monotonic() - start) * 1000)
      # For WS nodes, skip protocol probe (needs WS framing)
      latency = int((time.monotonic() - start) * 1000)
      return latency <= MAX_LATENCY, latency

    # Protocol-level probe (non-WS only)
    probe_ok = True
    if ptype == "trojan":
      probe_ok = _trojan_probe(sock, node.get("password", ""), TCP_TIMEOUT)
    elif ptype == "vless":
      probe_ok = _vless_probe(sock, node.get("uuid", ""), TCP_TIMEOUT)
    elif ptype in ("http", "socks5"):
      probe_ok = _http_probe(sock, TCP_TIMEOUT)
    # ss, ssr, vmess, hysteria2: just TCP+TLS

    latency = int((time.monotonic() - start) * 1000)
    return probe_ok and latency <= MAX_LATENCY, latency

  except Exception:
    return False, 9999
  finally:
    if sock:
      try:
        sock.close()
      except Exception:
        pass


def _is_field_complete(node: Dict) -> bool:
  if node.get("network") in ("ws", "websocket"):
    ws_opts = node.get("ws-opts") or {}
    if "path" not in ws_opts:
      return False
  if node.get("tls"):
    if not node.get("servername") and not node.get("sni"):
      return False
  ptype = node.get("type", "").lower()
  if ptype in ("http", "socks5"):
    if not node.get("username") or not node.get("password"):
      return False
  return True


def run(nodes: List[Dict]) -> List[Dict]:
  total = len(nodes)

  # Pre-filter: drop nodes with missing critical fields
  complete = [n for n in nodes if _is_field_complete(n)]
  dropped = total - len(complete)
  if dropped:
    print(f"  \u5b57\u6bb5\u4e0d\u5b8c\u6574\u629b\u5f03: {dropped}/{total}")

  print(f"  \u6b63\u5728\u6d4b\u8bd5 {len(complete)} \u4e2a\u8282\u70b9 (\u5e76\u53d1 {BATCH_SIZE})...")

  valid: List[Dict] = []
  with ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
    futures = {pool.submit(_test_one, n): n for n in complete}
    for f in as_completed(futures):
      node = futures[f]
      success, latency = f.result()
      if success:
        node["latency"] = latency
        valid.append(node)

  valid.sort(key=lambda x: x["latency"])
  print(f"  TCP\u901a\u8fc7: {len(valid)}/{len(complete)}")
  return valid
