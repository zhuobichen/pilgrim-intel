# Pilgrim Intel 🕊️

个人 AI 情报聚合系统 — 多信源热点新闻抓取 + LLM 分析 + 邮件推送。

## 🗂️ 项目结构

```
pilgrim-intel/
├── abstract-culture/   # 抽象文化热点追踪 (11 平台 → 深度文化分析)
├── trendradar/         # TrendRadar 热点聚合 (热榜+RSS → 报告+邮件)
├── gamehub/            # GameHub 游戏资讯日报 (15 游戏信源 → 精选摘要)
└── horizon/            # Horizon AI 新闻雷达 (中英双语日报)
```

## 📡 覆盖信源

| 项目 | 信源数 | 输出 |
|---|---|---|
| abstract-culture | ~15 | 文化分析日报 Markdown + 邮件 |
| trendradar | ~20+ | HTML 报告 + 多平台推送 |
| gamehub | 15 | 游戏资讯日报 + 邮件 |
| horizon | HackerNews + RSS | 中英双语日报 + GitHub Pages |

## 🚀 快速开始

每个子项目独立运行，详见各自目录下的 `requirements.txt`/`pyproject.toml`。

### 定时任务

各项目 `scripts/` 目录包含 `daily-run.bat` 和 `setup-scheduled-task.ps1`，默认每天 18:30 通过 Windows Task Scheduler 执行。

## 🔗 相关仓库

- [TrendRadar](https://github.com/Thysrael/Horizon)
- [Horizon](https://github.com/Thysrael/Horizon)
