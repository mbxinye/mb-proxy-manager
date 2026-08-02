# Proxy Manager

自动聚合多路代理订阅 → mihomo 端到端测试 → 生成 Clash 配置文件，通过 GitHub Actions 每小时自动更新。

## 项目结构

```
.
├── run.py                     # 入口
├── scripts/
│   ├── config.py              # 环境变量配置
│   ├── fetcher.py             # 下载订阅（urllib + ThreadPool）
│   ├── parser.py              # 解析 Base64 / YAML / URI（协议分发到 protocols/）
│   ├── protocols/             # 各协议解析与转换（SS/SSR/VMess/VLESS/Trojan/Hysteria2）
│   ├── clash_converter.py     # Clash 转换外观（委托 protocols registry）
│   ├── dedup.py               # 去重（registry dedup_key）
│   ├── country.py             # 国家识别 / CN relay 判定 / 节点命名
│   ├── geoip.py               # MaxMind GeoLite2 查询（按需下载）
│   ├── tester.py              # mihomo 端到端测试编排（两阶段验证）
│   ├── mihomo.py              # MihomoTester 协调器
│   ├── config_builder.py      # mihomo 测试配置构建
│   ├── latency_tester.py      # mihomo API 延迟测试
│   ├── mihomo_manager.py      # mihomo 二进制下载与缓存
│   ├── process_manager.py     # mihomo 进程生命周期管理
│   ├── output.py              # 生成 Clash YAML + URI 列表 + JSON
│   └── utils.py               # 工具函数
├── subscriptions.txt          # 订阅链接（每行一个，可带优先级）
├── output/
│   ├── clash_config.yml       # 200 最佳节点
│   ├── clash_mini.yml         # 100 最佳节点
│   ├── clash_all.yml          # 全量可用节点（不截断）
│   ├── nodes.txt              # 200 节点 URI 列表
│   ├── nodes_mini.txt         # 100 节点 URI 列表
│   ├── nodes_all.txt          # 全量节点 URI 列表（不截断）
│   └── valid_nodes.json       # 调试数据
└── .github/workflows/
    └── smart-proxy.yml        # 每小时自动运行 + 手动触发
```

## 快速开始

1. **Fork 本仓库**
2. **编辑 `subscriptions.txt`**，替换为你的订阅链接（每行一个，`#` 注释）

   支持格式：
   - Clash YAML（`proxies:` 字段）
   - Base64 编码订阅
   - SS / SSR / VMess / Trojan / VLESS / Hysteria2 URI 直链

   **订阅优先级**：在 URL 后加空格+数字，数字越大在输出排序中越靠前（默认 0）：
   ```
   https://example.com/high-quality-sub 10
   https://example.com/normal-sub
   ```

3. **手动触发首次运行**：Actions → Proxy Filter Updater → Run workflow
4. **启用 GitHub Pages** 后可通过以下链接订阅：

```
https://你的用户名.github.io/仓库名/clash.yml
https://你的用户名.github.io/仓库名/clash_all.yml
https://你的用户名.github.io/仓库名/clash_mini.yml
https://你的用户名.github.io/仓库名/nodes.txt
https://你的用户名.github.io/仓库名/nodes_all.txt
https://你的用户名.github.io/仓库名/nodes_mini.txt
```

> `clash_all.yml` / `nodes_all.txt` 为全量可用节点（不截断），适合需要最大节点池的场景。
> `nodes*.txt` 为纯文本逐行 URI 格式，Hiddify / v2rayN / NekoBox 等客户端可直接订阅。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PROXY_SUB_TIMEOUT` | 30 | 订阅下载超时（秒） |
| `PROXY_MAX_OUTPUT_NODES` | 200 | 完整版输出节点数 |
| `PROXY_MINI_OUTPUT_NODES` | 100 | 精简版输出节点数 |
| `PROXY_MIHOMO_VERSION` | v1.19.13 | mihomo 内核版本（按需下载，不提交进仓库） |
| `PROXY_TEST_URL` | https://www.gstatic.com/generate_204 | foreign 节点端到端测试 URL |
| `PROXY_TEST_URL_CN` | http://connect.rom.miui.com/generate_204 | CN relay stage-1 测试 URL（**必须为 204 端点**，非 204 如 baidu.com 会误杀全部 CN relay） |
| `PROXY_TEST_TIMEOUT` | 2000 | mihomo delay 测试超时（ms） |
| `PROXY_TEST_CONCURRENCY` | 100 | mihomo delay 并发测试数 |
| `PROXY_MAX_LATENCY` | 1500 | 拒绝延迟超过此值(ms)的节点，0=禁用 |
| `PROXY_RELAY_ENABLED` | true | 启用两阶段 China relay 验证 |
| `PROXY_RELAY_CONCURRENCY` | 50 | 经 China relay 测试时的并发数 |
| `PROXY_RELAY_MAX_RELAYS` | 5 | 尝试多少个 China relay（跨运营商覆盖） |
| `PROXY_RELAY_MAX_PER_RELAY` | 0 | 每个 relay 测试的节点上限（0=不限） |
| `PROXY_EXCLUDE_CN_OUTPUT` | true | 从最终输出中排除中国大陆节点 |
| `PROXY_GEOIP_DB` | `geoip/GeoLite2-Country.mmdb` | MaxMind GeoLite2-Country MMDB 路径 |
| `PROXY_GEOIP_DB_URL` | P3TERX latest release | MMDB 缺失或过期时自动下载的 URL |
| `PROXY_GEOIP_MAX_AGE_DAYS` | 35 | MMDB 超过此天数则重新下载 |
| `PROXY_GEOIP_DNS_WORKERS` | 20 | GeoIP 预取时的并行 DNS 解析数 |
| `PROXY_PREFERRED_COUNTRIES` | US,KR,JP,SG,HK,TW | 输出排序优先国家（逗号分隔） |

## 本地运行

```bash
pip3 install -r requirements.txt
python3 run.py
```

## 许可证

MIT
