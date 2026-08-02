#!/usr/bin/env python3
"""节点验证管线 - SRP：run() 仅编排，各阶段逻辑下沉到独立函数；DIP：依赖 MihomoTester 抽象。"""

from typing import Dict, List, Tuple

from scripts.config import (
  EXCLUDE_CN_OUTPUT,
  RELAY_ENABLED,
  RELAY_MAX_PER_RELAY,
  RELAY_MAX_RELAYS,
  TEST_URL_CN,
)
from scripts.country import is_china_node
from scripts.geoip import prefetch_countries
from scripts.log import get_logger
from scripts.mihomo import MihomoTester
from scripts.protocols._helpers import get_sni
from scripts.protocols.registry import get_registry


def _node_key(n: Dict) -> str:
  """稳定的节点标识，用于跨批次去重（替代脆弱的 id() 引用契约）。"""
  return get_registry().dedup_key(n)

log = get_logger("tester")


def _filter_complete(nodes: List[Dict]) -> List[Dict]:
  """预过滤：剔除协议必填凭证缺失的节点（mihomo 启动会 fatal 中断整批加载）。"""
  registry = get_registry()
  complete = [n for n in nodes if registry.is_field_complete(n)]
  dropped = len(nodes) - len(complete)
  if dropped:
    log.info(f"  字段不完整抛弃: {dropped}/{len(nodes)}")
  return complete


def _split_by_region(nodes: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
  """Stage-1 前分流 CN/foreign：CN 出口无法达 GFW 外目标，必须用国内 URL 测可达性。"""
  prefetch_countries([n.get("server", "") for n in nodes])
  china, foreign = [], []
  for n in nodes:
    if is_china_node(
      n.get("name", ""),
      n.get("server", ""),
      get_sni(n) or "",
    ):
      china.append(n)
    else:
      foreign.append(n)
  log.info(f"  分流: CN relay {len(china)} / foreign {len(foreign)}")
  return china, foreign


def _stage1(tester: MihomoTester, cn: List[Dict], foreign: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
  """Stage-1：CN relay 用国内 204 端点，foreign 用 gstatic（runner 为美国出口）。"""
  cn_valid = tester.test_nodes(cn, test_url=TEST_URL_CN) if cn else []
  foreign_valid = tester.test_nodes(foreign) if foreign else []
  log.info(f"  stage-1: {len(cn_valid) + len(foreign_valid)} reachable (CN relay {len(cn_valid)} / foreign {len(foreign_valid)})")
  return cn_valid, foreign_valid


def _stage2_relay(tester: MihomoTester, foreign: List[Dict], relays: List[Dict]) -> List[Dict]:
  """Stage-2：经 China relay 重新测 foreign（dialer-proxy），验证国内出口可达性。

  失败节点即国内不可用节点；逐 relay 尝试，任一 relay 通即保留。
  全部 relay 均无节点可达时回退 stage-1 foreign，保证仍有产出（标记为未经验证）。"""
  remaining = list(foreign)
  confirmed: List[Dict] = []
  for relay in relays:
    if not remaining:
      break
    # RELAY_MAX_PER_RELAY>0 时截断，但确保所有 remaining 至少被一个 relay 测试
    # （最后一个 relay 测全部剩余，避免未测节点被静默丢弃）
    if RELAY_MAX_PER_RELAY > 0 and relay is not relays[-1]:
      batch = remaining[:RELAY_MAX_PER_RELAY]
    else:
      batch = remaining
    relay_latency = relay.get("latency", 0) or 0
    log.info(f"  relay {relay.get('name', '')} ({relay_latency}ms) -> testing {len(batch)} remaining")
    got = tester.test_nodes_relay(batch, relay, relay_latency)
    got_keys = {_node_key(n) for n in got}
    confirmed.extend(got)
    remaining = [n for n in remaining if _node_key(n) not in got_keys]
    log.info(f"    confirmed {len(confirmed)} total, {len(remaining)} left")
  if not confirmed and foreign:
    log.warning(
      "  WARN 0 nodes reachable via relay; falling back to stage-1 foreign "
      "(these nodes are NOT verified for China-egress reachability)"
    )
    for n in foreign:
      n["_relay_unverified"] = True
    return list(foreign)
  return confirmed


def run(nodes: List[Dict]) -> List[Dict]:
  tester = MihomoTester()
  complete = _filter_complete(nodes)
  china_candidates, foreign_candidates = _split_by_region(complete)
  cn_valid, foreign_valid = _stage1(tester, china_candidates, foreign_candidates)

  if RELAY_ENABLED and cn_valid:
    relays = sorted(cn_valid, key=lambda x: x.get("latency", 9999))[:RELAY_MAX_RELAYS]
    foreign_valid = _stage2_relay(tester, foreign_valid, relays)
  else:
    log.info("  no China relay available; skipping stage-2 (using stage-1 results)")

  final = list(foreign_valid)
  if not EXCLUDE_CN_OUTPUT:
    final.extend(cn_valid)
  final.sort(key=lambda x: x.get("latency", 9999))
  return final
