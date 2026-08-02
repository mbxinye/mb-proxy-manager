#!/usr/bin/env python3
"""国家识别 / CN relay 判定 / 节点命名 - SRP：聚合所有地理标记相关逻辑。

LKP：对外仅暴露 extract_country / is_china_node / generate_node_name；
GeoIP 查询通过 geoip.server_country 延迟导入，调用方无需感知。"""

import re
from typing import Optional


COUNTRY_KEYWORDS = {
  "hong kong": "HK", "hk": "HK", "香港": "HK",
  "japan": "JP", "jp": "JP", "日本": "JP",
  "singapore": "SG", "sg": "SG", "新加坡": "SG",
  "usa": "US", "us": "US", "united states": "US", "美国": "US",
  "korea": "KR", "kr": "KR", "韩国": "KR",
  "taiwan": "TW", "tw": "TW", "台湾": "TW",
  "uk": "GB", "gb": "GB", "united kingdom": "GB", "英国": "GB",
  "germany": "DE", "de": "DE", "德国": "DE",
  "france": "FR", "fr": "FR", "法国": "FR",
  "australia": "AU", "au": "AU", "澳大利亚": "AU",
  "canada": "CA", "ca": "CA", "加拿大": "CA",
  "netherlands": "NL", "nl": "NL", "荷兰": "NL",
  "italy": "IT", "it": "IT", "意大利": "IT",
  "spain": "ES", "es": "ES", "西班牙": "ES",
  "brazil": "BR", "br": "BR", "巴西": "BR",
  "india": "IN", "印度": "IN",
  "russia": "RU", "ru": "RU", "俄罗斯": "RU",
  "vietnam": "VN", "vn": "VN", "越南": "VN",
  "thailand": "TH", "th": "TH", "泰国": "TH",
  "indonesia": "ID", "id": "ID", "印尼": "ID",
  "malaysia": "MY", "my": "MY", "马来西亚": "MY",
  "philippines": "PH", "ph": "PH", "菲律宾": "PH",
  "finland": "FI", "芬兰": "FI",
  "sweden": "SE", "瑞典": "SE",
  "turkey": "TR", "土耳其": "TR",
  "ukraine": "UA", "乌克兰": "UA",
  "poland": "PL", "波兰": "PL",
  "argentina": "AR", "阿根廷": "AR",
  "chile": "CL", "智利": "CL",
  "mexico": "MX", "墨西哥": "MX",
  "south africa": "ZA", "南非": "ZA",
  "united arab emirates": "AE", "阿联酋": "AE",
  "israel": "IL", "以色列": "IL",
  "portugal": "PT", "葡萄牙": "PT",
  "switzerland": "CH", "瑞士": "CH",
  "austria": "AT", "奥地利": "AT",
  "belgium": "BE", "比利时": "BE",
  "denmark": "DK", "丹麦": "DK",
  "norway": "NO", "挪威": "NO",
  "czech": "CZ", "捷克": "CZ",
  "romania": "RO", "罗马尼亚": "RO",
  "bulgaria": "BG", "保加利亚": "BG",
  "greece": "GR", "希腊": "GR",
  "mongolia": "MN", "蒙古": "MN",
  "kazakhstan": "KZ", "哈萨克斯坦": "KZ",
  "qatar": "QA", "卡塔尔": "QA",
  "saudi arabia": "SA", "沙特": "SA",
  "china": "CN", "cn": "CN", "中国": "CN", "大陆": "CN", "国内": "CN",
  "移动": "CN", "电信": "CN", "联通": "CN", "中转": "CN",
  "mainland": "CN", "回国": "CN", "落地": "CN",
  "beijing": "CN", "shanghai": "CN", "guangzhou": "CN", "shenzhen": "CN",
  "chengdu": "CN", "chongqing": "CN", "nanjing": "CN", "hangzhou": "CN",
  "wuhan": "CN", "xian": "CN", "qingdao": "CN",
}

COUNTRY_FLAGS = {
  "HK": "🇭🇰", "JP": "🇯🇵", "SG": "🇸🇬", "US": "🇺🇸",
  "KR": "🇰🇷", "TW": "🇹🇼", "GB": "🇬🇧", "DE": "🇩🇪",
  "FR": "🇫🇷", "AU": "🇦🇺", "CA": "🇨🇦", "NL": "🇳🇱",
  "IT": "🇮🇹", "ES": "🇪🇸", "BR": "🇧🇷", "IN": "🇮🇳",
  "RU": "🇷🇺", "VN": "🇻🇳", "TH": "🇹🇭", "ID": "🇮🇩",
  "MY": "🇲🇾", "PH": "🇵🇭",
  "FI": "🇫🇮", "SE": "🇸🇪", "TR": "🇹🇷", "UA": "🇺🇦",
  "PL": "🇵🇱", "AR": "🇦🇷", "CL": "🇨🇱", "MX": "🇲🇽",
  "ZA": "🇿🇦", "AE": "🇦🇪", "IL": "🇮🇱", "PT": "🇵🇹",
  "CH": "🇨🇭", "AT": "🇦🇹", "BE": "🇧🇪", "DK": "🇩🇰",
  "NO": "🇳🇴", "CZ": "🇨🇿", "RO": "🇷🇴", "BG": "🇧🇬",
  "GR": "🇬🇷", "MN": "🇲🇳", "KZ": "🇰🇿", "QA": "🇶🇦",
  "SA": "🇸🇦",
  "CN": "🇨🇳",
}

# Regional indicator range: U+1F1E6 (A) .. U+1F1FF (Z)
_FLAG_START = 0x1F1E6

# 城市/机场代码 → 国家（云厂商机房命名常见，如 do-lon1, do-syd1）
CITY_CODE_MAP = {
  "lon": "GB", "lhr": "GB", "man": "GB",
  "syd": "AU", "mel": "AU", "per": "AU",
  "nrt": "JP", "kix": "JP", "tyo": "JP",
  "sin": "SG", "sgp": "SG",
  "hkg": "HK",
  "icn": "KR", "sel": "KR",
  "tpe": "TW",
  "lax": "US", "sfo": "US", "sea": "US", "nyc": "US", "ord": "US",
  "iad": "US", "dfw": "US", "atl": "US", "mia": "US", "sjc": "US",
  "yyz": "CA", "yvr": "CA",
  "fra": "DE", "ber": "DE", "dus": "DE",
  "cdg": "FR", "par": "FR", "mrs": "FR",
  "ams": "NL",
  "mad": "ES", "bcn": "ES",
  "mil": "IT", "rom": "IT", "fco": "IT",
  "arn": "SE", "got": "SE",
  "hel": "FI",
  "osl": "NO",
  "cph": "DK",
  "waw": "PL",
  "otp": "RO",
  "svo": "RU", "dme": "RU", "led": "RU",
  "ist": "TR",
  "dxb": "AE",
  "bom": "IN", "del": "IN",
  "gru": "BR", "sao": "BR",
  "mex": "MX",
  "bkk": "TH",
  "kul": "MY",
  "cgk": "ID",
  "mnl": "PH",
  "hnl": "US",
}


def _flag_emoji_to_code(name: str) -> Optional[str]:
  for i in range(len(name) - 1):
    a, b = ord(name[i]), ord(name[i + 1])
    if _FLAG_START <= a <= _FLAG_START + 25 and _FLAG_START <= b <= _FLAG_START + 25:
      return chr(a - _FLAG_START + ord("A")) + chr(b - _FLAG_START + ord("A"))
  return None


# 预编译匹配正则：ASCII 关键词用 \b 词边界（避免 "in" 匹配 "Singapore"）；
# 中文关键词无 \b 概念，用普通子串匹配。
# 两字母缩写歧义高（"in"/"us"/"de" 等），仅保留全称与中文。
_COUNTRY_KEYWORD_RES = []
for _kw, _code in COUNTRY_KEYWORDS.items():
  if _kw.isascii():
    _COUNTRY_KEYWORD_RES.append((re.compile(rf"\b{re.escape(_kw)}\b", re.IGNORECASE), _code))
  else:
    _COUNTRY_KEYWORD_RES.append((re.compile(re.escape(_kw)), _code))

# 城市码预编译：要求前后为非字母（- _ 数字 空格 边界），避免 "man" 匹配 "germany"
_CITY_CODE_RES = [
  (re.compile(rf"(?<![a-z]){re.escape(code)}(?![a-z])"), country)
  for code, country in CITY_CODE_MAP.items()
]


def _keyword_to_country(text: str) -> Optional[str]:
  """词边界匹配 ASCII 关键词、子串匹配中文关键词，避免短码误匹配。"""
  for pattern, code in _COUNTRY_KEYWORD_RES:
    if pattern.search(text):
      return code
  return None


def _city_code_to_country(text: str) -> Optional[str]:
  text_lower = text.lower()
  for pattern, country in _CITY_CODE_RES:
    if pattern.search(text_lower):
      return country
  return None


def _detect_country_code(name: str, server: str = "", sni: str = "") -> Optional[str]:
  """公共国别探测链：flag emoji → 关键词 → 城市码(server/sni) → GeoIP。

  extract_country 与 is_china_node 共用此链，消除重复实现。"""
  code = _flag_emoji_to_code(name)
  if code:
    return code
  code = _keyword_to_country(name)
  if code:
    return code
  if server:
    code = _city_code_to_country(server)
    if code:
      return code
  if sni:
    code = _city_code_to_country(sni)
    if code:
      return code
  # Fallback: real GeoIP on the server address -> covers bare-IP / unknown hosts.
  from scripts.geoip import server_country
  return server_country(server)


def extract_country(name: str, server: str = "", sni: str = "") -> Optional[str]:
  return _detect_country_code(name, server, sni)


def generate_node_name(code: str, index: int, latency: int) -> str:
  """生成显示名。code 由调用方预先探测（避免重复探测与 GeoIP 丢失）。"""
  code = code or "XX"
  flag = COUNTRY_FLAGS.get(code, "")
  latency_str = str(min(latency, 9999))
  if flag:
    return f"{flag} {code} {index:02d} [{latency_str}]"
  return f"{code} {index:02d} [{latency_str}]"


# Mainland-CN relay detection must be precise: false positives exclude usable
# foreign nodes and mis-pick a non-China relay (no GFW traversal). We treat
# HK/TW as foreign exits and never classify them as China.
_NON_CN_HINTS = ("hong kong", "hongkong", "hk", "taiwan", "taipei", "tw")


def is_china_node(name: str, server: str = "", sni: str = "") -> bool:
  name = name or ""
  server = server or ""
  sni = sni or ""
  name_lower = name.lower()
  for hint in _NON_CN_HINTS:
    if hint in name_lower:
      return False
  code = _detect_country_code(name, server, sni)
  if code:
    return code == "CN"
  return False
