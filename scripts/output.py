#!/usr/bin/env python3
"""输出模块 - SRP：write() 仅编排，子函数各司排序/命名/转换/写文件/统计。

修复：拆分 write() 的 6 项职责；print 改 logging。"""

import json
from pathlib import Path
from typing import Dict, List

import yaml

from scripts.clash_converter import to_clash_node, to_uri
from scripts.config import PREFERRED_COUNTRIES
from scripts.country import extract_country, generate_node_name
from scripts.log import get_logger
from scripts.protocols._helpers import get_sni

log = get_logger("output")

OUTPUT_DIR = Path("output")
PROTOCOL_PRIORITY = {
  "hysteria2": 1, "trojan": 2, "tuic": 3, "vless-reality": 4, "vless": 5,
  "vmess": 6, "anytls": 7, "ss": 8, "ssr": 9,
  "socks5": 10, "http": 11,
}

_COUNTRY_RANK = {code: i for i, code in enumerate(PREFERRED_COUNTRIES)}


def _country_rank(node: Dict) -> int:
  code = extract_country(
    node.get("name", ""),
    node.get("server", ""),
    get_sni(node) or "",
  )
  return _COUNTRY_RANK.get(code, 99) if code else 99


def _protocol_rank(n: Dict) -> int:
  ptype = n.get("type", "").lower()
  if ptype == "vless" and n.get("reality-opts"):
    ptype = "vless-reality"
  return PROTOCOL_PRIORITY.get(ptype, 999)


def _sort_key(n: Dict) -> tuple:
  return (
    -n.get("_sub_priority", 0),
    _country_rank(n),
    _protocol_rank(n),
    n.get("latency", 9999),
  )


def _build_config(proxies: List[Dict]) -> Dict:
  """构建 Clash 配置模板（消除 full/mini/all 重复）"""
  return {
    "port": 7890,
    "socks-port": 7891,
    "allow-lan": True,
    "mode": "rule",
    "log-level": "warning",
    "proxies": proxies,
    "proxy-groups": [
      {"name": "Proxy", "type": "select", "proxies": [p["name"] for p in proxies]},
    ],
    "rules": ["MATCH,Proxy"],
  }


def _write_uris(path: Path, nodes: List[Dict]):
  """写入 URI 列表文件"""
  uris = [u for u in (to_uri(n) for n in nodes) if u]
  with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(uris) + ("\n" if uris else ""))
  log.info(f"  ✓ {path.name} ({len(uris)} 节点)")


def _write_clash_config(path: Path, proxies: List[Dict]):
  """写入 Clash YAML 配置"""
  config = _build_config(proxies)
  with open(path, "w", encoding="utf-8") as f:
    f.write("---\n")
    yaml.dump(config, f, allow_unicode=True, sort_keys=False, indent=2)
  log.info(f"  ✓ {path.name} ({len(proxies)} 节点)")


def _rename_nodes(valid_nodes: List[Dict]) -> None:
  """一次性为全量节点生成显示名（避免重复命名、保证 full/all 编号一致）。"""
  counters: Dict[str, int] = {}
  for node in valid_nodes:
    name = node.get("name", f"Node_{node['server']}")
    code = extract_country(
      name,
      node.get("server", ""),
      get_sni(node) or "",
    ) or "XX"
    counters[code] = counters.get(code, 0) + 1
    node["name"] = generate_node_name(name, counters[code], node.get("latency", 9999))


def _write_outputs(valid_nodes: List[Dict], max_full: int, max_mini: int) -> None:
  """写全部输出文件（full/mini/all + uri + debug json）。"""
  selected = valid_nodes[:max_full]
  clash_nodes = [to_clash_node(n) for n in selected]

  # Full config
  _write_clash_config(OUTPUT_DIR / "clash_config.yml", clash_nodes)
  # Mini config
  _write_clash_config(OUTPUT_DIR / "clash_mini.yml", clash_nodes[:max_mini])
  # Plain URI lists (Hiddify-compatible) — full / mini
  _write_uris(OUTPUT_DIR / "nodes.txt", selected)
  _write_uris(OUTPUT_DIR / "nodes_mini.txt", selected[:max_mini])
  # Debug JSON
  with open(OUTPUT_DIR / "valid_nodes.json", "w", encoding="utf-8") as f:
    json.dump(selected, f, indent=2, ensure_ascii=False)
  log.info(f"  ✓ valid_nodes.json")
  # All configs (uncapped)
  all_clash_nodes = [to_clash_node(n) for n in valid_nodes]
  _write_clash_config(OUTPUT_DIR / "clash_all.yml", all_clash_nodes)
  _write_uris(OUTPUT_DIR / "nodes_all.txt", valid_nodes)


def _print_stats(selected: List[Dict]) -> None:
  """打印节点类型统计。"""
  type_counts: Dict[str, int] = {}
  for n in selected:
    t = n.get("type", "unknown")
    type_counts[t] = type_counts.get(t, 0) + 1
  for t, c in sorted(type_counts.items()):
    log.info(f"    {t.upper()}: {c}")


def write(valid_nodes: List[Dict], max_full: int, max_mini: int):
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  valid_nodes.sort(key=_sort_key)
  _rename_nodes(valid_nodes)
  _write_outputs(valid_nodes, max_full, max_mini)
  _print_stats(valid_nodes[:max_full])
