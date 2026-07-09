#!/usr/bin/env python3


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
}

COUNTRY_FLAGS = {
  "HK": "🇭🇰", "JP": "🇯🇵", "SG": "🇸🇬", "US": "🇺🇸",
  "KR": "🇰🇷", "TW": "🇹🇼", "GB": "🇬🇧", "DE": "🇩🇪",
  "FR": "🇫🇷", "AU": "🇦🇺", "CA": "🇨🇦", "NL": "🇳🇱",
  "IT": "🇮🇹", "ES": "🇪🇸", "BR": "🇧🇷", "IN": "🇮🇳",
  "RU": "🇷🇺", "VN": "🇻🇳", "TH": "🇹🇭", "ID": "🇮🇩",
  "MY": "🇲🇾", "PH": "🇵🇭",
}


def extract_country(name: str) -> str | None:
  name_lower = name.lower()
  for keyword, code in COUNTRY_KEYWORDS.items():
    if keyword in name_lower:
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
