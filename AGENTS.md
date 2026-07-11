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
| `PROXY_TEST_URL` | http://www.gstatic.com/generate_204 | URL used for real end-to-end proxy test |
| `PROXY_TEST_TIMEOUT` | 2000 | mihomo delay-test timeout (ms) |
| `PROXY_TEST_CONCURRENCY` | 100 | Concurrent mihomo delay tests |

### GitHub Actions

Runs every 3 hours via `.github/workflows/smart-proxy.yml`.
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
