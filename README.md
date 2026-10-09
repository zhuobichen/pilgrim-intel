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
| shenlun | 37 | 考公申论时政素材（`standalone`：单独一封邮件，不并入合并日报） |

### shenlun 独立频道说明

`feeds.yaml` 里 `push: {standalone: true}` 的 feed 不并入合并邮件：它照常抓取并写入
同一个 SQLite 库（可用 `run.py search` 与 MCP 检索），但自己单独发一封邮件。

- **信源 37 个**：央媒（人民日报/新华网/央视/求是/光明/经济日报/中国青年报/中国日报）、
  部委行业报（工人日报/农民日报/科技日报/中国环境报/中国教育报）、党建理论（共产党员网/
  旗帜网/学习时报）、市场化与地方（澎湃/界面/观察者网/新京报/北京日报/中国网/中国新闻周刊/
  上观=解放日报/半月谈/中新网）、政策源（政府网 RSS + 政策文件库 JSON）。
- **抓取方式**：`type` 支持 `rss` / `html` / `api`(JSON) / `govpolicy` / `thepaper` /
  `cctv` / `cenews`；HTML 源的选择器写在 `source.extra.item`（以 `/` 开头按 XPath 解析）。
- **正文增强**：31 个源抓文章正文（`enrich` 配置），AI 不再只能靠标题编。
- **防编造**：prompt 约束 + 生成后 `_verify_digest` 机器核对文号与关键数字。
- **取材按字符预算**（`enrich.context_chars`）而非固定条数，调大取材量也不会撑爆上下文。
- ⚠️ **国内多数时政媒体的 RSS 已停更**（人民网停在 2025-06、新华网停在 2022-12），
  只看 HTTP 状态码会采到陈年旧闻；引擎内置 `_check_freshness` 会对疑似停更的源告警。
