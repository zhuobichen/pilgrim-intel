# Pilgrim Intel 🕊️ v2.0

统一 AI 情报聚合系统 — 多信源抓取 → SQLite 持久化 → AI 摘要 → 多推送 → MCP 可查询。

## 🏗️ 架构

```
feeds.yaml (4个feed配置)
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
python run.py --feed gamehub

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

## ⭐ 反馈系统

邮件中每条新闻附带 [like] / [dislike] 链接，点击后自动记录到 SQLite，
帮助 AI 学习你的偏好。

## 🕐 定时任务

Windows Task Scheduler: `PilgrimIntelDaily` → 每天 18:30 执行 `scripts/daily-run.bat`

## 📡 覆盖信源 (43 个)

| Feed | 信源数 | 输出 |
|------|--------|------|
| abstract-culture | 16 | 热点文化分析日报 |
| trendradar | 8 | 新闻简报 |
| gamehub | 12 | 游戏资讯日报 |
| horizon | 7 | 科技新闻双语日报 |
