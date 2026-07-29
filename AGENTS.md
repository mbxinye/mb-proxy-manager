# AGENTS.md

## Build/Lint/Test Commands

### Setup and Installation

```bash
pip3 install -r requirements.txt
```

### Run

```bash
python3 run.py
```

### Test

```bash
python3 -c "from scripts.parser import NodeParser; print('OK')"
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROXY_SUB_TIMEOUT` | 30 | Subscription fetch timeout (seconds) |
| `PROXY_MAX_OUTPUT_NODES` | 200 | Max output nodes |
| `PROXY_MINI_OUTPUT_NODES` | 100 | Mini output nodes |
| `PROXY_MIHOMO_VERSION` | v1.19.13 | mihomo kernel version (downloaded on demand) |
| `PROXY_TEST_URL` | https://www.gstatic.com/generate_204 | URL used for foreign-node end-to-end test |
| `PROXY_TEST_URL_CN` | http://connect.rom.miui.com/generate_204 | URL used for CN-relay stage-1 test (must be a 204 endpoint reachable from China egress; non-204 responses cause mihomo delay-test to report failure) |
| `PROXY_TEST_TIMEOUT` | 2000 | mihomo delay-test timeout (ms) |
| `PROXY_TEST_CONCURRENCY` | 100 | Concurrent mihomo delay tests |
| `PROXY_MAX_LATENCY` | 1500 | Reject nodes with latency above this (ms), 0=disable |
| `PROXY_RELAY_ENABLED` | true | Enable two-stage China-relay verification |
| `PROXY_RELAY_CONCURRENCY` | 50 | Delay-test concurrency when tunneling through a China relay |
| `PROXY_RELAY_MAX_RELAYS` | 5 | How many China relays to try (best coverage across carriers) |
| `PROXY_RELAY_MAX_PER_RELAY` | 0 | Cap nodes tested per relay (0 = no cap) |
| `PROXY_EXCLUDE_CN_OUTPUT` | true | Exclude mainland-China nodes from the final output |

### GeoIP (China-relay detection)

| Variable | Default | Description |
|---|---|---|
| `PROXY_GEOIP_DB` | `geoip/GeoLite2-Country.mmdb` | Path to the MaxMind GeoLite2-Country MMDB |
| `PROXY_GEOIP_DB_URL` | P3TERX latest release | URL auto-downloaded when the MMDB is missing or stale |
| `PROXY_GEOIP_MAX_AGE_DAYS` | 35 | Re-download the MMDB if older than this (days) |
| `PROXY_GEOIP_DNS_WORKERS` | 20 | Parallel host-to-IP resolutions during geoip prefetch |
### GitHub Actions

Runs every hour via `.github/workflows/smart-proxy.yml` (`13 */1 * * *`).
Manual trigger also supported via `workflow_dispatch`.

## Code Style Guidelines

### Import Organization

1. Standard library
2. Third-party (yaml)
3. Local (`from scripts.xxx import yyy`)

### Formatting

- 2-space indentation
- Max line length: ~120
- No docstrings unless necessary
- No unnecessary comments

### Type Hints

Use `Dict`, `List`, `Optional`, `Tuple` from typing where helpful.

### Naming

- snake_case for functions/variables
- UPPER_SNAKE_CASE for constants
- Private: single underscore prefix

### String Formatting

f-strings only.

## Project Architecture

- `scripts/config.py` — env-based config
- `scripts/fetcher.py` — download subscriptions via `urllib` + `ThreadPoolExecutor`
- `scripts/parser.py` — parse Base64 / YAML / URI formats. YAML field whitelist covers all protocol-required fields (ssr `protocol`/`obfs`/params, hysteria2 `obfs`/`up`/`down`, `grpc-opts`/`h2-opts`, `alpn`); URI parsers extract `obfs`/`alpn`/`up`/`down` for hysteria2 and `alpn` for vless/trojan. Clash config detection scans the full content for `proxies:`/`proxy-groups:` (a 30-line window missed full Clash configs where `proxies:` appears after `mixed-port`/`dns`/`rules`, causing the entire YAML to be skipped line-by-line). `parse_all` reports per-URL skip counts to surface malformed subscriptions.
- `scripts/tester.py` — mihomo kernel end-to-end tunnel test (downloads binary on demand). `_is_field_complete` pre-filters nodes missing protocol-required credentials; TLS nodes without explicit sni are kept (mihomo falls back to `server`); reality nodes must carry `public-key`.
- `scripts/geoip.py` — MaxMind GeoLite2-Country lookup (downloads MMDB on demand, caches DNS). CN-relay identification runs text heuristics on node names first (covers self-described `中转`/`上海` relays); when inconclusive, `is_china_node`/`extract_country` fall back to GeoIP on the resolved `server` IP. The MMDB is downloaded once and reused (`PROXY_GEOIP_MAX_AGE_DAYS`); GitHub Actions caches it per day so only the first run of each day re-downloads.
Two-stage verification pipeline:

1. Stage-1 splits nodes into CN-relay candidates and foreign exit nodes **before** testing, because CN egress cannot reach GFW-blocked targets (e.g. `gstatic.com`). CN candidates are tested against `PROXY_TEST_URL_CN` (default `connect.rom.miui.com/generate_204`, a 204 endpoint — non-204 URLs like `baidu.com` cause mihomo delay-test to fail and silently kill all CN relay candidates); foreign nodes against `PROXY_TEST_URL` (default `gstatic/generate_204`). Both tests run from the GitHub Actions runner (US egress).
2. The `PROXY_RELAY_MAX_RELAYS` fastest subscription CN nodes become stage-2 relays.
3. Stage-2 re-tests every foreign node through each China relay via mihomo `dialer-proxy`, so the tested path is `runner -> China relay -> foreign node -> 204` — i.e. reachability from a China egress. Nodes that fail here are exactly the ones unusable from China and are dropped. Relays are tried in order; a node only needs to be reachable via one.
4. China relay nodes are excluded from the final output by default (`PROXY_EXCLUDE_CN_OUTPUT`). Falls back to stage-1 results when no relay is available.
- `scripts/output.py` — generate Clash YAML (clash_config.yml, clash_mini.yml, clash_all.yml) + plain URI list (nodes.txt, nodes_mini.txt, nodes_all.txt)
- `scripts/main.py` — pipeline orchestration
- `run.py` — thin entry point

### Output

- `output/clash_config.yml` — full config (200 nodes) for Karing/Hiddify subscription
- `output/clash_mini.yml` — 100 best nodes
- `output/clash_all.yml` — all valid nodes (uncapped)
- `output/nodes.txt` — plain text, 200 URIs; Hiddify/v2rayN/NekoBox compatible
- `output/nodes_mini.txt` — plain text, 100 URIs
- `output/nodes_all.txt` — plain text, all valid URIs (uncapped)
- `output/valid_nodes.json` — debug data

### Subscription Sources

URLs in `subscriptions.txt`, one per line, `#` for comments.
Optional priority after URL (space-separated, higher = sorted first, default 0):
`https://example.com/sub 10`

### Protocols

SS (SIP008 + old format), SSR, VMess, Trojan, VLESS (incl. Reality), Hysteria2.
