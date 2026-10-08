# Pilgrim Intel 🕊️ v2.0

统一 AI 情报聚合系统 — 多信源抓取 → SQLite 持久化 → AI 摘要 → 多推送 → MCP 可查询。

## 🏗️ 架构

```
feeds.yaml (5 个 feed 配置；其中 shenlun 为独立邮件频道)
    │
    ▼
run.py  ──►  pilgrim/engine.py  ──►  pilgrim/storage.py (SQLite + FTS5)
    │              │                         │
    ▼              ▼                         ▼
统一Runner    fetch→dedup→AI→push       pilgrim/server.py
                                        (MCP + HTTP 反馈)
```

## 📦 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入 DEEPSEEK_API_KEY + 邮箱配置

# 运行所有 feed
python run.py

# 运行单个 feed
python run.py run --feed gamehub

# 搜索已存储内容
python run.py search "AI 新闻"

# 查看统计
python run.py stats

# 启动 MCP + 反馈服务器
python run.py serve
```

## 🌐 MCP Server

启动服务器后访问 `http://localhost:9876/mcp`，提供 5 个工具：

| 工具 | 功能 |
|------|------|
| `pilgrim_search_news` | 全文搜索已收录内容 |
| `pilgrim_get_digest` | 获取指定日期日报 |
| `pilgrim_list_sources` | 列出所有信源 |
| `pilgrim_get_stats` | 统计概览 |
| `pilgrim_get_trending` | 最新热门 |

## 📊 统计面板

`http://localhost:9876/stats` — 实时查看各 feed 收录量、Top 信源、用户反馈

## ⭐ 反馈系统（邮件中已移除按钮）

`/rate` 端点与 SQLite 的 `feedback` 表仍保留，但邮件和报告里**不再显示** `[like]` / `[dislike]`
按钮——个人使用没有意义，已从版式中去掉。

## 🕐 定时任务

Windows Task Scheduler: `PilgrimIntelDaily` → 每天 18:30 执行 `scripts/daily-run.bat`

## 📡 覆盖信源

| Feed | 信源数 | 输出 |
|------|--------|------|
| abstract-culture | 7 | 热点文化分析日报 |
| trendradar | 10 | 新闻简报 |
| gamehub | 15 | 游戏资讯日报 |
| horizon | 18 | 科技新闻双语日报 |
| shenlun | 25 | 考公申论时政素材（`standalone`：单独一封邮件，不并入合并日报） |

### shenlun 独立频道说明

`feeds.yaml` 里 `push: {standalone: true}` 的 feed 不并入合并邮件：它照常抓取并写入
同一个 SQLite 库（可用 `run.py search` 与 MCP 检索），但自己单独发一封邮件。
信源以中国政府网 RSS（政策文件）为中坚，中新网（时政/理论评论）、光明网时评、
半月谈、经济日报为辅；这些站的 RSS 多已停更，故用 `type: html` 抓列表页，
选择器写在 `source.extra.item` 里。
