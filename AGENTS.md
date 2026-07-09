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
| `PROXY_TCP_TIMEOUT` | 3 | TCP connection test timeout (seconds) |
| `PROXY_BATCH_SIZE` | 200 | Concurrent TCP tests |
| `PROXY_MAX_LATENCY` | 5000 | Max allowed latency (ms) |
| `PROXY_MAX_OUTPUT_NODES` | 100 | Max output nodes |
| `PROXY_MINI_OUTPUT_NODES` | 30 | Mini output nodes |

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
- `scripts/tester.py` — TCP socket connect test via `ThreadPoolExecutor`
- `scripts/output.py` — generate Clash YAML (clash_config.yml, clash_mini.yml)
- `scripts/main.py` — pipeline orchestration
- `run.py` — thin entry point

### Output

- `output/clash_config.yml` — full config (100 nodes) for Karing/Hiddify subscription
- `output/clash_mini.yml` — 30 best nodes
- `output/valid_nodes.json` — debug data

### Subscription Sources

URLs in `subscriptions.txt`, one per line, `#` for comments.

### Protocols

SS (SIP008 + old format), SSR, VMess, Trojan, VLESS (incl. Reality), Hysteria2.
