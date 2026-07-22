#!/usr/bin/env python3

from typing import Optional


def sanitize_name(name: str) -> str:
  if not name:
    return "Node"
  sanitized = name.encode("ascii", "ignore").decode("ascii")
  sanitized = "".join(c for c in sanitized if 32 <= ord(c) <= 126)
  invalid_chars = [
    ":", "{", "}", "[", "]", ",", "&", "*",
    "?", "|", "-", "<", ">", "=", "!", "%",
    "@", "\\", "/", " ", "'", '"', "#", "$",
    "^", "+", "~", "`",
  ]
  for c in invalid_chars:
    sanitized = sanitized.replace(c, "_")
  sanitized = sanitized.strip("_")
  if not sanitized or not sanitized[0].isalpha():
    sanitized = "Node_" + sanitized
  return sanitized[:50] or "Node"


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
  "india": "IN", "in": "IN", "印度": "IN",
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
  "cgk": "ID", "sin": "SG",
  "mnl": "PH",
  "hnl": "US",
}


def _flag_emoji_to_code(name: str) -> Optional[str]:
  for i in range(len(name) - 1):
    a, b = ord(name[i]), ord(name[i + 1])
    if _FLAG_START <= a <= _FLAG_START + 25 and _FLAG_START <= b <= _FLAG_START + 25:
      return chr(a - _FLAG_START + ord("A")) + chr(b - _FLAG_START + ord("A"))
  return None


def _city_code_to_country(text: str) -> Optional[str]:
  text_lower = text.lower()
  for city_code, country in CITY_CODE_MAP.items():
    if city_code in text_lower:
      return country
  return None


def extract_country(name: str, server: str = "", sni: str = "") -> Optional[str]:
  code = _flag_emoji_to_code(name)
  if code:
    return code
  name_lower = name.lower()
  for keyword, code in COUNTRY_KEYWORDS.items():
    if keyword in name_lower:
      return code
  if server:
    code = _city_code_to_country(server)
    if code:
      return code
  if sni:
    code = _city_code_to_country(sni)
    if code:
      return code
  return None


def generate_node_name(name: str, index: int, latency: int) -> str:
  country = extract_country(name)
  code = country or "XX"
  flag = COUNTRY_FLAGS.get(code, "")
  latency_str = str(min(latency, 9999))
  if flag:
    return f"{flag} {code} {index:02d} [{latency_str}]"
  return f"{code} {index:02d} [{latency_str}]"
