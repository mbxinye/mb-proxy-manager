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
| `PROXY_TEST_URL` | https://www.gstatic.com/generate_204 | URL used for real end-to-end proxy test |
| `PROXY_TEST_TIMEOUT` | 2000 | mihomo delay-test timeout (ms) |
| `PROXY_TEST_CONCURRENCY` | 100 | Concurrent mihomo delay tests |
| `PROXY_MAX_LATENCY` | 1500 | Reject nodes with latency above this (ms), 0=disable |
| `PROXY_RELAY_ENABLED` | true | Enable two-stage China-relay verification |
| `PROXY_RELAY_CONCURRENCY` | 50 | Delay-test concurrency when tunneling through a China relay |
| `PROXY_RELAY_MAX_RELAYS` | 5 | How many China relays to try (best coverage across carriers) |
| `PROXY_RELAY_MAX_PER_RELAY` | 0 | Cap nodes tested per relay (0 = no cap) |
| `PROXY_EXCLUDE_CN_OUTPUT` | true | Exclude mainland-China nodes from the final output |

### External China-relay sources

When the subscription pool has few mainland-China nodes, free-proxy aggregators
supply extra candidate relays. They are scraped, stage-1 tested from the runner
(must be alive and tunnel to `gstatic/generate_204`, i.e. CONNECT/SOCKS5-connect
capable), then tried in stage-2 AFTER subscription CN relays. They never enter
the final output.

| Variable | Default | Description |
|---|---|---|
| `PROXY_RELAY_EXTERNAL_ENABLED` | true | Fetch external CN-relay candidates and use them in stage-2 |
| `PROXY_RELAY_EXTERNAL_SOURCES` | `freevpnnode` | Comma list of source keys (currently `freevpnnode`) |
| `PROXY_RELAY_EXTERNAL_PAGES` | 3 | Pages to scrape per source |
| `PROXY_RELAY_EXTERNAL_PROTOCOLS` | `socks5,http` | Proxy protocols to keep (socks4 is dropped; mihomo has no socks4 outbound) |
| `PROXY_RELAY_EXTERNAL_MAX` | 5 | How many external relays to try in stage-2 |
| `PROXY_RELAY_EXTERNAL_LATENCY` | 2500 | Stage-1 latency cap (ms) for external relays (looser than node output) |

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
- `scripts/parser.py` — parse Base64 / YAML / URI formats
- `scripts/tester.py` — mihomo kernel end-to-end tunnel test (downloads binary on demand)
- `scripts/geoip.py` — MaxMind GeoLite2-Country lookup (downloads MMDB on demand, caches DNS). CN-relay identification runs text heuristics on node names first (covers self-described `中转`/`上海` relays); when inconclusive, `is_china_node`/`extract_country` fall back to GeoIP on the resolved `server` IP. The MMDB is downloaded once and reused (`PROXY_GEOIP_MAX_AGE_DAYS`); GitHub Actions caches it per day so only the first run of each day re-downloads.
- `scripts/relay_sources.py` — fetches external mainland-China relay candidates from free-proxy aggregators (default: `cn.freevpnnode.com/free-proxy-for-china/`). Scrapes the HTML table, builds mihomo `http`/`socks5` outbounds (socks4 dropped), and dedupes. `tester.run` stage-1 tests them from the runner before they may be used as `dialer-proxy` relays; they never enter the final output.
Two-stage verification pipeline:

1. Stage-1 direct end-to-end tunnel test (GitHub Actions runner, US egress) picks reachable nodes.
2. Identifies mainland-China nodes as candidate relays.
3. Phase-1 relays = the `PROXY_RELAY_MAX_RELAYS` fastest subscription CN nodes. Phase-2 relays = external candidates (`scripts/relay_sources.py`) that pass their own stage-1 test. If the subscription pool has few CN nodes, external relays are what keeps stage-2 meaningful.
4. Stage-2 re-tests every foreign node through the China relay via mihomo `dialer-proxy`, so the tested path is `runner -> China relay -> foreign node -> 204` — i.e. reachability from a China egress. Nodes that fail here are exactly the ones unusable from China and are dropped. Phase-1 (subscription) relays are tried before external free-proxy relays.
5. Up to `PROXY_RELAY_MAX_RELAYS` subscription relays + `PROXY_RELAY_EXTERNAL_MAX` external relays are tried in order so a node only needs to be reachable via one of them.
6. China relay nodes are excluded from the final output by default (`PROXY_EXCLUDE_CN_OUTPUT`). External free-proxy relays are never output. Falls back to stage-1 results when no relay is available.
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
