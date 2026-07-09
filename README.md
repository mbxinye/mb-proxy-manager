# 智能代理配置管理器

自动化的代理节点聚合与管理系统，支持智能评分、节点验证和自动生成Clash配置。

## 功能特性

### 智能订阅管理
- **智能评分系统**: 基于成功率、节点质量、数量稳定性等多维度评分
- **动态频率控制**: 根据评分自动调整订阅使用频率（每日/经常/偶尔/暂停）
- **优胜劣汰机制**: 自动淘汰低质量订阅，优先使用高质量订阅

### 节点处理流程
1. **多源聚合**: 支持SS/SSR/VMess/Trojan/VLESS等主流格式
2. **智能去重**: 基于服务器+端口+协议自动去重
3. **有效性验证**: TCP连接测试+延迟检测
4. **优选排序**: 按延迟排序，保留最优节点

### 配置输出
- **完整版**: 50个精选节点，完整分流规则
- **精简版**: 20个最优节点，适合移动端
- **GitHub Pages**: 自动部署，直接订阅使用

## 🎯 严格模式 - 适用于 Shadowrocket

本系统采用**最严格的 TCP 连接测试**，确保每个节点都真实可用，特别适合 Shadowrocket 等高要求场景。

### 严格模式特点

- ✅ **TCP连接测试**: 真实的端口连通性测试，不是DNS解析
- ✅ **高可用性**: 只有能建立TCP连接的节点才会被保留
- ✅ **精确延迟**: 测量真实的网络延迟
- ✅ **Shadowrocket兼容**: 完全支持所有代理类型(SS/SSR/VMess/VLESS/Trojan)

### 有效率说明

严格模式下有效率通常在 **5-30%** 是正常的，因为：
- 免费节点的端口经常被防火墙屏蔽
- 进行真实的TCP连接测试（不是简单的ping）
- 超过2秒延迟的连接会被过滤

**解决方案**: 添加更多订阅源，确保有足够可用的节点。

📖 **详细说明**: [SHADOWROCKET.md](./SHADOWROCKET.md)

---

## 本地测试（推荐）

在部署到GitHub之前，强烈建议先在本地测试。我们推荐使用 **uv**（极速 Python 包管理器）：

### 使用 uv（推荐，快 10-100 倍）

```bash
# 1. 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 编辑订阅链接
vim subscriptions.txt

# 3. 一键测试（严格模式，TCP连接测试）
./test_uv.sh

# 4. 查看状态
uv run python check_status.py
```

### 使用 pip（传统方式）

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 编辑订阅链接
vim subscriptions.txt

# 3. 运行测试
./test.sh

# 4. 查看状态
python3 check_status.py
```

### 自定义超时配置

如果订阅获取经常超时，或需要调整测试速度：

```bash
# 增加订阅获取超时时间
PROXY_SUB_TIMEOUT=60 ./test.sh

# 增加TCP连接超时时间（慢速网络）
PROXY_TCP_TIMEOUT=10 ./test.sh

# 加快测试速度（快速网络）
PROXY_BATCH_SIZE=50 PROXY_BATCH_DELAY=0.3 ./test.sh
```

📚 详细文档：
- **[LOCAL_TEST.md](./LOCAL_TEST.md)** - 完整的本地测试文档
- **[UV_GUIDE.md](./UV_GUIDE.md)** - uv 详细使用指南
- **[TIMEOUT_CONFIG.md](./TIMEOUT_CONFIG.md)** - 超时配置完整指南

## 快速开始

### 1. 准备工作

Fork此仓库，然后：

```bash
# 克隆你的仓库
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 2. 添加订阅链接

编辑 `subscriptions.txt` 文件，每行添加一个订阅链接：

```text
# 你的订阅链接
https://example1.com/subscription1
https://example2.com/subscription2
https://example3.com/clash.yaml
```

### 3. 启用GitHub Actions

1. 进入仓库 Settings → Actions → General
2. 确保 "Workflow permissions" 设置为 "Read and write permissions"
3. 点击 "Save"

### 4. 启用GitHub Pages

1. 进入仓库 Settings → Pages
2. Source 选择 "Deploy from a branch"
3. Branch 选择 "gh-pages" → "/ (root)"
4. 点击 "Save"

### 5. 手动触发首次运行

进入 Actions → Smart Proxy Config Updater → Run workflow

## 使用配置

### Clash 订阅链接

运行成功后，你可以使用以下链接：

```
https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/clash.yml
https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/clash_mini.yml
```

### 自动更新

系统每天自动运行一次（北京时间早上8点），无需手动干预。

## 评分系统详解

### 评分维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 成功率 | 40% | 节点可用比例 |
| 平均延迟 | 30% | 节点响应速度 |
| 节点数量 | 20% | 订阅提供的节点数 |
| 更新频率 | 10% | 订阅更新稳定性 |

### 使用频率分级

| 分数 | 频率 | 说明 |
|------|------|------|
| 90-100 | daily | 每次都使用 |
| 70-89 | often | 2/3概率使用 |
| 50-69 | sometimes | 1/3概率使用 |
| 30-49 | rarely | 每周一次 |
| <30 | suspended | 暂停使用 |

### 新订阅保护

新加入的订阅前3次必定被测试，之后根据表现评分。

## 目录结构

```
.
├── .github/workflows/
│   └── smart-proxy.yml          # GitHub Actions工作流
├── scripts/
│   ├── subscription_manager.py  # 订阅管理
│   ├── validator.py             # 节点验证
│   └── clash_generator.py       # 配置生成
├── data/
│   ├── subscriptions.json       # 订阅数据库
│   └── score_history.json       # 评分历史
├── subscriptions.txt            # 订阅链接列表（用户编辑）
└── README.md                    # 本文件
```

## 分流规则

### 代理组

- 🚀 **节点选择**: 手动选择节点
- ♻️ **自动选择**: URL测试自动选择最优节点
- 🔯 **故障转移**: 自动切换到可用节点
- 📹 **油管视频**: YouTube相关流量
- 🎥 **奈飞视频**: Netflix相关流量
- 🌍 **国外媒体**: 海外流媒体和服务
- 🌏 **国内媒体**: 国内视频平台
- 📢 **谷歌FCM**: Google服务
- Ⓜ️ **微软服务**: Microsoft相关
- 🍎 **苹果服务**: Apple相关
- 🎮 **游戏平台**: Steam/Epic等
- 🛑 **广告拦截**: 广告和追踪
- 🐟 **漏网之鱼**: 其他流量

### 规则策略

- 局域网IP直连
- 中国大陆IP直连
- 微软服务可配置
- 国内视频平台直连
- 其他流量自动代理

## GitHub Actions额度

- **免费额度**: 每月2000分钟
- **单次运行**: 约8-15分钟（取决于订阅数量和节点数）
- **建议频率**: 每天一次（cron: `0 0 * * *` UTC）

## 故障排查

### 配置未更新

1. 检查 Actions 是否运行成功
2. 查看运行日志中的错误信息
3. 确认订阅链接是否有效

### 节点数量过少

1. 检查 `subscriptions.txt` 中的链接是否有效
2. 查看验证统计了解节点有效率
3. 增加更多订阅源

### 评分异常

1. 检查 `data/subscriptions.json` 中的数据
2. 查看历史记录 `data/score_history.json`
3. 新订阅需要3次测试后才能准确评分

## 安全提示

⚠️ **重要**: 本系统仅用于管理你自己的订阅链接。请勿：
- 分享包含他人订阅的仓库
- 将私人订阅链接提交到公共仓库
- 泄露你的代理配置信息

## 许可证

MIT License

## 致谢

- [Clash](https://github.com/Dreamacro/clash) - 优秀的代理工具
- [GitHub Actions](https://github.com/features/actions) - 自动化工作流