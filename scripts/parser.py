#!/usr/bin/env python3
"""订阅解析器 - SRP：NodeParser 只负责订阅文本 → 内部节点 dict；
URI 分派委托 protocols 注册表（OCP），Base64/YAML 为本模块私有职责。

修复：异常收窄（YAML 解析失败用 yaml.YAMLError）；_proxy_to_node 的 name
在 try 外预赋值避免 except 引用未定义变量；print 改 logging。"""

from typing import Dict, List, Optional

import yaml

from scripts.log import get_logger
from scripts.protocols._helpers import try_base64_decode
from scripts.protocols.registry import get_registry

log = get_logger("parser")


class NodeParser:
  """订阅解析器：Base64 / Clash YAML / URI 行混合输入。"""

  def __init__(self):
    self._skipped = 0
    self._registry = get_registry()

  def parse_subscription(self, content: str) -> List[Dict]:
    nodes: List[Dict] = []
    content = content.strip()
    if not content:
      return nodes

    # 仅当全文不含 URI scheme 时才尝试 Base64 解码（避免误伤 URI 列表）
    if "://" not in content:
      decoded = try_base64_decode(content)
      if decoded:
        content = decoded

    # Clash 配置判定：全文扫描 proxies:/proxy-groups:（早期 30 行窗口会漏掉
    # mixed-port/dns/rules 之后的 proxies，导致整份 YAML 被当 URI 逐行跳过）
    if "proxies:" in content or "proxy-groups:" in content:
      nodes = self._parse_yaml(content)
    else:
      for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith(("#", "//")):
          continue
        node = self._registry.parse(line)
        if node:
          nodes.append(node)
        else:
          self._skipped += 1
    return nodes

  @staticmethod
  def _fix_yaml_flow_quotes(content: str) -> str:
    """修复 YAML flow mapping 中未转义的双引号。

    处理形如 {name: "🇫🇷FR-"2001:bc"} 的问题——节点名含 " 但未转义，
    导致 PyYAML 把 "🇫🇷FR-" 当作完整引号字符串，然后被 2001:bc 弄晕。
    必要性：真实订阅源常含此类脏数据，不修复则整份 YAML 解析失败。
    """
    result = []
    in_flow = False
    in_quote = False
    i = 0
    while i < len(content):
      c = content[i]
      if c == '{':
        in_flow = True
        result.append(c)
      elif c == '}':
        in_flow = False
        in_quote = False
        result.append(c)
      elif c == '"' and in_flow:
        if not in_quote:
          in_quote = True
          result.append(c)
        else:
          # 判断当前 " 是否为闭合引号：后面紧跟 , } 或行尾空格+逗号/花括号
          j = i + 1
          while j < len(content) and content[j] in ' \t\r\n':
            j += 1
          if j < len(content) and content[j] in ',}':
            in_quote = False
            result.append(c)
          else:
            # 未转义的内嵌引号 → 转义
            result.append('\\"')
      elif c == '\\' and in_flow and in_quote and i + 1 < len(content):
        # 已转义字符，跳过下一个
        result.append(c)
        i += 1
        result.append(content[i])
      else:
        result.append(c)
      i += 1
    return ''.join(result)

  def _parse_yaml(self, content: str) -> List[Dict]:
    """解析 Clash YAML（支持多文档 --- 分隔）。

    三级回退：原文 safe_load_all → 修引号后 safe_load_all → 单文档 safe_load。
    区分「解析成功但无节点」与「解析失败」：前者直接返回，后者进入下一级。"""
    nodes = self._extract_from_docs(content)
    if nodes is not None:
      return nodes
    fixed = self._fix_yaml_flow_quotes(content)
    if fixed != content:
      nodes = self._extract_from_docs(fixed)
      if nodes is not None:
        return nodes
    try:
      data = yaml.safe_load(fixed)
      if isinstance(data, dict):
        return self._proxies_from_list(data.get("proxies", []) or [])
    except yaml.YAMLError:
      pass
    return []

  def _extract_from_docs(self, content: str) -> Optional[List[Dict]]:
    """safe_load_all 成功返回节点列表（可能为空）；抛异常返回 None。"""
    try:
      nodes: List[Dict] = []
      for doc in yaml.safe_load_all(content):
        if not isinstance(doc, dict):
          continue
        nodes.extend(self._proxies_from_list(doc.get("proxies", []) or []))
      return nodes
    except yaml.YAMLError:
      return None

  def _proxies_from_list(self, proxies) -> List[Dict]:
    nodes: List[Dict] = []
    for proxy in proxies:
      if not isinstance(proxy, dict):
        continue
      node = self._proxy_to_node(proxy)
      if node:
        nodes.append(node)
    return nodes

  def _proxy_to_node(self, proxy: Dict) -> Optional[Dict]:
    """Clash proxy dict → 内部节点格式。"""
    name = proxy.get("name", "Unknown")[:50]  # 预赋值，避免 except 引用未定义变量
    try:
      ptype = proxy.get("type", "").lower()
      server = proxy.get("server", "")
      port = proxy.get("port", 0)
      if not server or not port:
        return None
      # 容错脏端口（上游 YAML 可能写入 "443?" 等带 query 的字符串）
      port = int(str(port).split("?")[0].strip())
      node: Dict = {
        "type": ptype,
        "name": name,
        "server": server,
        "port": port,
      }
      # 字段白名单覆盖各协议必需字段
      for field in [
        "uuid", "password", "cipher", "alterId", "network", "tls", "sni", "flow",
        "udp", "ws-opts", "servername", "client-fingerprint", "skip-cert-verify",
        "username",
        "protocol", "obfs", "protocol-param", "obfs-param",
        "grpc-opts", "h2-opts", "alpn",
        "obfs-password", "insecure", "up", "down",
      ]:
        if field in proxy:
          node[field] = proxy[field]
      if ptype == "vmess":
        node["security"] = proxy.get("cipher", "auto")
      elif ptype == "vless":
        if "reality-opts" in proxy:
          node["reality-opts"] = proxy["reality-opts"]
          node["client-fingerprint"] = proxy.get("client-fingerprint", "chrome")
      elif ptype == "trojan":
        node["skip-cert-verify"] = proxy.get("skip-cert-verify", False)
      return node
    except (ValueError, KeyError, TypeError, AttributeError) as e:
      log.warning(f"  ⚠ 节点转换失败: {name} ({e})")
      return None


def parse_all(results: List[dict]) -> List[Dict]:
  parser = NodeParser()
  all_nodes: List[Dict] = []
  per_url_skip = []
  for r in results:
    if not r["success"] or not r.get("content"):
      continue
    before = parser._skipped
    nodes = parser.parse_subscription(r["content"])
    delta = parser._skipped - before
    if delta > 0:
      per_url_skip.append((r["url"], delta))
    for n in nodes:
      n["_sub_url"] = r["url"]
    all_nodes.extend(nodes)
  log.info(f"  解析完成: {len(all_nodes)} 个节点")
  if parser._skipped:
    log.info(f"  解析跳过: {parser._skipped} 行无效/不支持")
    log.info("  跳过明细 (URL | skip数):")
    for url, n in sorted(per_url_skip, key=lambda x: -x[1]):
      log.info(f"    [{n:>6}] {url[:60]}")
  return all_nodes
