#!/usr/bin/env python3
"""
GeoIP 服务实现 - 单一职责(SRP) + 最少知识原则(LKP)

封装所有 GeoIP 相关逻辑，对外提供简洁接口。
"""

import socket
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, Optional

from scripts.config import (
  GEOIP_DB_PATH,
  GEOIP_DB_URL,
  GEOIP_DNS_WORKERS,
  GEOIP_MAX_AGE_DAYS,
)
from scripts.log import get_logger

log = get_logger("geoip")


class LRUCache:
    """线程安全的 LRU 缓存 - 解决缓存无限增长问题。

    用哨兵 _MISSING 区分「未命中」与「命中但值为 None」（如 DNS 解析失败），
    避免 None 值被反复重新查询。"""
    _MISSING = object()

    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str, default=None):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return default

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._cache

    def put(self, key: str, value) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)


class GeoIPService:
    """GeoIP 服务实现 - SRP: 只负责地理位置查询"""
    _MISSING = object()  # 哨兵：区分缓存未命中与值为 None

    def __init__(self, max_cache_size: int = 10000):
        self._reader = None
        self._reader_failed = False
        self._lock = threading.Lock()
        self._dns_cache = LRUCache(max_cache_size)
        self._country_cache = LRUCache(max_cache_size)
    
    def _ensure_db(self) -> Optional[Path]:
        """确保 GeoIP 数据库存在且有效"""
        path = Path(GEOIP_DB_PATH)
        if path.exists():
            age_days = (time.time() - path.stat().st_mtime) / 86400
            if age_days < GEOIP_MAX_AGE_DAYS:
                return path
        
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"  下载 GeoIP 数据库: {GEOIP_DB_URL}")
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
            log.info(f"  ✓ GeoIP 就绪: {path} ({path.stat().st_size // 1024} KB)")
            return path
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            log.warning(f"  ⚠ GeoIP 下载失败: {str(e)[:100]}")
            if path.exists():
                return path
            return None
    
    def _get_reader(self):
        """获取数据库读取器（线程安全）"""
        with self._lock:
            if self._reader is not None:
                return self._reader
            if self._reader_failed:
                return None
            try:
                import maxminddb
                path = self._ensure_db()
                if not path or not path.exists():
                    self._reader_failed = True
                    return None
                self._reader = maxminddb.open_database(str(path))
                return self._reader
            except (OSError, ImportError, ValueError) as e:
                log.warning(f"  ⚠ GeoIP 加载失败: {str(e)[:100]}")
                self._reader_failed = True
                return None
    
    def _resolve_ip(self, server: str) -> Optional[str]:
        """解析域名到 IP（带缓存，None 值也会被缓存避免重复查询）"""
        cached = self._dns_cache.get(server, self._MISSING)
        if cached is not self._MISSING:
            return cached
        
        ip = None
        try:
            socket.inet_aton(server)
            ip = server
        except OSError:
            try:
                infos = socket.getaddrinfo(server, None, socket.AF_INET)
                if infos:
                    ip = infos[0][4][0]
            except (socket.gaierror, OSError, UnicodeError, ValueError):
                # UnicodeError: IDNA 编码超长/非法 label；ValueError: 非法主机名
                ip = None
        
        self._dns_cache.put(server, ip)
        return ip
    
    def get_country(self, server: str) -> Optional[str]:
        """获取服务器所属国家代码"""
        if not server:
            return None

        cached = self._country_cache.get(server, self._MISSING)
        if cached is not self._MISSING:
            return cached
        
        ip = self._resolve_ip(server)
        code = None
        if ip:
            reader = self._get_reader()
            if reader:
                try:
                    rec = reader.get(ip)
                    if rec and isinstance(rec, dict):
                        country = rec.get("country")
                        if country:
                            code = country.get("iso_code")
                except (KeyError, TypeError, ValueError):
                    code = None
        
        self._country_cache.put(server, code)
        return code
    
    def prefetch(self, servers: Iterable[str]) -> None:
        """预取多个服务器的国家信息"""
        from concurrent.futures import ThreadPoolExecutor
        
        uniq = list(dict.fromkeys(servers))
        if not uniq:
            return
        
        self._get_reader()
        if self._reader_failed:
            return
        
        with ThreadPoolExecutor(max_workers=GEOIP_DNS_WORKERS) as pool:
            list(pool.map(self.get_country, uniq))
        
        log.info(f"  GeoIP 预取 {len(uniq)} 个主机")


# 全局单例
_geoip_service: Optional[GeoIPService] = None
_geoip_lock = threading.Lock()


def get_geoip_service() -> "GeoIPService":
    """获取 GeoIP 服务单例"""
    global _geoip_service
    with _geoip_lock:
        if _geoip_service is None:
            _geoip_service = GeoIPService()
        return _geoip_service


def reset_geoip_service() -> None:
    """测试钩子：重置 GeoIP 单例，便于注入 mock 或重新初始化。"""
    global _geoip_service
    with _geoip_lock:
        _geoip_service = None


def set_geoip_service(service: "GeoIPService") -> None:
    """测试钩子：注入自定义 GeoIP 服务（依赖倒置，便于测试替换）。"""
    global _geoip_service
    with _geoip_lock:
        _geoip_service = service


def prefetch_countries(servers: Iterable[str]) -> None:
    """便捷函数：预取国家信息"""
    get_geoip_service().prefetch(servers)


def server_country(server: str) -> Optional[str]:
    """便捷函数：获取服务器国家"""
    return get_geoip_service().get_country(server)
