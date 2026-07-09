# Proxy Manager

自动聚合多路代理订阅 → TCP 连通性测试 → 生成 Clash 配置文件，通过 GitHub Actions 每 3 小时自动更新。

## 项目结构

```
.
├── run.py                     # 入口
├── scripts/
│   ├── config.py              # 环境变量配置
│   ├── fetcher.py             # 下载订阅（urllib + ThreadPool）
│   ├── parser.py              # 解析 SS/SSR/VMess/Trojan/VLESS/Hysteria2
│   ├── tester.py              # TCP 连接测试（ThreadPool）
│   ├── output.py              # 生成 Clash YAML + JSON
│   └── utils.py                 # 国家识别、名称生成
├── subscriptions.txt          # 订阅链接（每行一个）
├── output/
│   ├── clash_config.yml       # 50 最佳节点
│   ├── clash_mini.yml         # 30 最佳节点
│   └── valid_nodes.json       # 调试数据
└── .github/workflows/
    └── smart-proxy.yml        # 每 3 小时自动运行 + 手动触发
```

## 快速开始

1. **Fork 本仓库**
2. **编辑 `subscriptions.txt`**，替换为你的订阅链接（每行一个，`#` 注释）

   支持格式：
   - Clash YAML（`proxies:` 字段）
   - Base64 编码订阅
   - SS / SSR / VMess / Trojan / VLESS / Hysteria2 URI 直链

3. **手动触发首次运行**：Actions → Proxy Filter Updater → Run workflow
4. **启用 GitHub Pages** 后可通过以下链接订阅：

```
https://你的用户名.github.io/仓库名/clash.yml
https://你的用户名.github.io/仓库名/clash_mini.yml
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PROXY_SUB_TIMEOUT` | 30 | 订阅下载超时（秒） |
| `PROXY_MAX_OUTPUT_NODES` | 100 | 完整版输出节点数 |
| `PROXY_MINI_OUTPUT_NODES` | 30 | 精简版输出节点数 |
| `PROXY_MIHOMO_VERSION` | v1.19.13 | mihomo 内核版本（按需下载，不提交进仓库） |
| `PROXY_TEST_URL` | http://www.gstatic.com/generate_204 | 端到端真实代理测试用的 URL |
| `PROXY_TEST_TIMEOUT` | 2000 | mihomo delay 测试超时（ms） |
| `PROXY_TEST_CONCURRENCY` | 100 | mihomo delay 并发测试数 |

## 本地运行

```bash
pip3 install -r requirements.txt
python3 run.py
```

## 许可证

MIT