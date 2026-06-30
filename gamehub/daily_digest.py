#!/usr/bin/env python3
"""GameHub 每日游戏资讯摘要 — 15+ 信源 + DeepSeek AI + 邮件推送

信源列表:
  🇨🇳 国内:  B站游戏区 / B站热门 / B站动画 / B站科技 / 小黑盒 / 游研社 / 机核
  🌍 国外:  Eurogamer / PCGamer / RockPaperShotgun / VG247 / GameSpot /
           TouchArcade / GameInformer
  🔧 可选:  Steam 新闻 (需 STEAM_API_KEY + STEAM_ID)
"""

import asyncio
import json
import os
import re
import smtplib
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import httpx
from openai import OpenAI

# ── Config ─────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
CACHE_DIR = Path.home() / ".gamehub"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")
STEAM_ID = os.getenv("STEAM_ID", "")

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.qq.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

AI = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"


# ═══════════════════════════════════════════════════════
#  RSS Parser (unified)
# ═══════════════════════════════════════════════════════
def _tag(el: ET.Element) -> str:
    """Extract tag name without namespace."""
    return el.tag.split("}", 1)[1] if "}" in el.tag else el.tag


async def fetch_rss(name: str, url: str, limit: int = 15) -> list:
    """Generic RSS/Atom fetcher → [{title, url, desc, _source, _score}]"""
    items = []
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": UA},
                                     follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200:
                return items
            root = ET.fromstring(r.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.iter("item"):
                item = {}
                for child in entry:
                    t = _tag(child)
                    if t == "title":
                        item["title"] = (child.text or "").strip()
                    elif t == "link":
                        item["url"] = (child.text or child.get("href", "")).strip()
                    elif t in ("description", "encoded"):
                        item["desc"] = (child.text or "")[:200].strip()
                    elif t == "pubDate":
                        item["pub_date"] = (child.text or "").strip()
                if item.get("title") and len(item["title"]) > 3:
                    item["_source"] = name
                    item["_score"] = 80  # RSS 质量内容默认分
                    items.append(item)
            # Also try Atom format
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                item = {}
                for child in entry:
                    t = _tag(child)
                    if t == "title":
                        item["title"] = (child.text or "").strip()
                    elif t == "link":
                        item["url"] = (child.get("href", "") or child.text or "").strip()
                    elif t in ("summary", "content"):
                        item["desc"] = (child.text or "")[:200].strip()
                    elif t == "published":
                        item["pub_date"] = (child.text or "").strip()
                if item.get("title") and len(item["title"]) > 3:
                    item["_source"] = name
                    item["_score"] = 80
                    items.append(item)
    except Exception:
        return items
    return items[:limit]


# ═══════════════════════════════════════════════════════
#  Bilibili API
# ═══════════════════════════════════════════════════════
async def fetch_bilibili_all() -> list:
    """B站 游戏/热门/动画/科技 四大区 + 热门综合，去重合并"""
    all_items = []
    async with httpx.AsyncClient(timeout=20, headers={
        "User-Agent": UA, "Referer": "https://www.bilibili.com/"
    }) as c:

        # 分区排行
        zones = [(4, "B站游戏"), (1, "B站动画"), (188, "B站科技")]
        for rid, label in zones:
            try:
                r = await c.get("https://api.bilibili.com/x/web-interface/ranking/v2",
                               params={"rid": rid, "type": "all"})
                data = r.json()
                if data.get("code") != 0:
                    continue
                for v in (data.get("data") or {}).get("list", [])[:12]:
                    all_items.append({
                        "title": v.get("title", ""),
                        "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
                        "views": v.get("play", 0),
                        "likes": v.get("pts", 0),
                        "author": v.get("author", ""),
                        "_source": label,
                        "_score": v.get("pts", 0),
                    })
            except Exception:
                continue

        # 热门综合榜
        try:
            r = await c.get("https://api.bilibili.com/x/web-interface/popular",
                           params={"pn": 1, "ps": 25})
            data = r.json()
            for v in (data.get("data") or {}).get("list", [])[:20]:
                all_items.append({
                    "title": v.get("title", ""),
                    "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
                    "views": v.get("stat", {}).get("view", 0),
                    "likes": v.get("stat", {}).get("like", 0),
                    "author": v.get("owner", {}).get("name", ""),
                    "_source": "B站热门",
                    "_score": v.get("stat", {}).get("view", 0),
                })
        except Exception:
            pass

    # 去重
    seen, unique = set(), []
    for item in sorted(all_items, key=lambda x: x["_score"], reverse=True):
        t = item["title"]
        if t not in seen and len(t) > 2:
            seen.add(t)
            unique.append(item)
    return unique[:40]


# ═══════════════════════════════════════════════════════
#  小黑盒 API
# ═══════════════════════════════════════════════════════
async def fetch_xiaoheihe() -> list:
    items = []
    try:
        async with httpx.AsyncClient(timeout=15, headers={
            "User-Agent": UA_MOBILE,
            "Referer": "https://www.xiaoheihe.cn/"
        }) as c:
            r = await c.get("https://api.xiaoheihe.cn/bbs/web/home",
                          params={"limit": 25, "offset": 0})
            data = r.json()
            for link in (data.get("result") or {}).get("links", [])[:20]:
                title = link.get("title", "")
                if not title or len(title) < 4:
                    continue
                items.append({
                    "title": title,
                    "url": f"https://www.xiaoheihe.cn/app/bbs/{link.get('link_id','')}",
                    "likes": link.get("likes_count", 0),
                    "comments": link.get("comments_count", 0),
                    "_source": "小黑盒",
                    "_score": link.get("likes_count", 0) + link.get("comments_count", 0) * 3,
                })
    except Exception:
        pass
    return sorted(items, key=lambda x: x["_score"], reverse=True)[:15]


# ═══════════════════════════════════════════════════════
#  Steam (optional)
# ═══════════════════════════════════════════════════════
async def fetch_steam_library() -> list:
    if not STEAM_API_KEY or not STEAM_ID:
        return []
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(
                    "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                    params={"key": STEAM_API_KEY, "steamid": STEAM_ID,
                            "include_appinfo": 1, "include_played_free_games": 1, "format": "json"})
                games = r.json().get("response", {}).get("games", [])
                if games:
                    return games
        except Exception:
            await asyncio.sleep(2)
    return []


async def fetch_steam_news(games: list, top_n: int = 10) -> list:
    sorted_g = sorted(games, key=lambda g: g.get("playtime_forever", 0), reverse=True)
    news, seen = [], set()
    async with httpx.AsyncClient(timeout=15) as c:
        for g in sorted_g[:top_n]:
            app_id = g.get("appid")
            if not app_id:
                continue
            try:
                r = await c.get("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/",
                               params={"appid": app_id, "count": 2, "maxlength": 300, "format": "json"})
                for item in r.json().get("appnews", {}).get("newsitems", []):
                    u = item.get("url", "")
                    if u and u not in seen:
                        seen.add(u)
                        item["_game"] = g.get("name", f"App {app_id}")
                        item["_source"] = "Steam"
                        item["_score"] = item.get("date", 0)
                        news.append(item)
            except Exception:
                continue
    return sorted(news, key=lambda n: n.get("date", 0), reverse=True)[:20]


# ═══════════════════════════════════════════════════════
#  ALL RSS Sources
# ═══════════════════════════════════════════════════════
RSS_FEEDS = [
    # 🇨🇳 国内
    ("游研社", "https://www.yystv.cn/rss/feed"),
    ("机核", "https://www.gcores.com/rss"),
    # 🌍 国外
    ("Eurogamer", "https://www.eurogamer.net/feed"),
    ("PCGamer", "https://www.pcgamer.com/rss/"),
    ("RockPaperShotgun", "https://www.rockpapershotgun.com/feed"),
    ("VG247", "https://www.vg247.com/feed"),
    ("GameSpot", "https://www.gamespot.com/feeds/mashup/"),
    ("TouchArcade", "https://toucharcade.com/feed/"),
    ("GameInformer", "https://www.gameinformer.com/rss.xml"),
]


# ═══════════════════════════════════════════════════════
#  AI Digest
# ═══════════════════════════════════════════════════════
def ai_digest(all_items: list) -> str:
    by_source = {}
    for item in all_items:
        src = item.get("_source", "其他")
        by_source.setdefault(src, []).append(item)

    feed_text = []
    for src, batch in by_source.items():
        feed_text.append(f"\n### {src}（{len(batch)}条）")
        for i, item in enumerate(batch[:10], 1):
            game = item.get("_game", "")
            prefix = f"[{game}] " if game else ""
            author = item.get("author", "")
            auth = f" @{author}" if author else ""
            feed_text.append(
                f"{i}. {prefix}{item['title']}{auth}\n"
                f"   {item.get('url', '')}"
            )

    today = datetime.now().strftime("%Y年%m月%d日")
    prompt = f"""你是资深游戏编辑。请从以下多平台游戏资讯中选出 **10-15 条**最值得关注的内容，生成今日游戏日报（{today}）。

要求:
1. 每条包含: 吸睛标题(可改写)、1-2句中文摘要、来源平台 + 链接
2. 按重要性/热度排序，最重要的排最前面
3. 末尾加「🔥 今日热门话题」：总结1-2个今日最热的游戏话题
4. 末尾加「💡 编辑推荐」：推荐1条最值得深度阅读的
5. Markdown 格式，风格活泼专业，适当用emoji，全文中文

{chr(10).join(feed_text[:100])}"""

    try:
        r = AI.chat.completions.create(
            model="deepseek-chat",
            max_tokens=3500,
            temperature=0.5,
            messages=[
                {"role": "system", "content": "你是专业的游戏/科技资讯编辑，擅长从海量信息中筛选最有价值的新闻。输出Markdown格式，语言生动有料。"},
                {"role": "user", "content": prompt},
            ],
        )
        return r.choices[0].message.content
    except Exception as e:
        return _fallback(all_items) + f"\n\n> ⚠️ AI 摘要失败: {e}"


def _fallback(items: list) -> str:
    top = sorted(items, key=lambda x: x.get("_score", 0), reverse=True)[:15]
    md = f"## 🎮 今日游戏热门\n\n> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    for i, item in enumerate(top, 1):
        g = item.get("_game", "")
        src = item.get("_source", "")
        url = item.get("url", "")
        title = item.get("title", "")[:100]
        md += f"### {i}. {('**['+g+']** ' if g else '')}{title}\n"
        md += f"   {src}"
        if url:
            md += f" | [链接]({url})"
        md += "\n\n"
    return md


# ═══════════════════════════════════════════════════════
#  HTML Email
# ═══════════════════════════════════════════════════════
def build_html(digest_md: str, stats: dict) -> str:
    body = digest_md
    body = re.sub(r'^### (.+)$', r'<h3 style="color:#374151;margin:20px 0 8px;font-size:16px">\1</h3>', body, flags=re.M)
    body = re.sub(r'^## (.+)$', r'<h2 style="color:#1f2937;margin:24px 0 10px;border-bottom:2px solid #e5e7eb;padding-bottom:6px;font-size:18px">\1</h2>', body, flags=re.M)
    body = re.sub(r'^# (.+)$', r'<h1 style="color:#111827;margin:0 0 8px;font-size:20px">\1</h1>', body, flags=re.M)
    body = re.sub(r'\*\*(.+?)\*\*', r'<b style="color:#1f2937">\1</b>', body)
    body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#4f46e5;text-decoration:none;font-weight:500">\1</a>', body)
    body = re.sub(r'`([^`]+)`', r'<code style="background:#eff6ff;color:#2563eb;padding:2px 6px;border-radius:4px;font-size:13px">\1</code>', body)
    body = body.replace("\n\n", "<br><br>").replace("\n", "<br>")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    source_list = ", ".join(f"{k}({v})" for k, v in stats.items() if v > 0)

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei','Segoe UI',sans-serif;background:#f3f4f6;color:#1f2937;padding:0;margin:0">
<div style="max-width:680px;margin:0 auto;padding:24px 16px">

<div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:14px;padding:28px 24px;margin-bottom:20px;text-align:center;box-shadow:0 4px 12px rgba(79,70,229,0.15)">
  <div style="font-size:32px;margin-bottom:4px">🎮</div>
  <h1 style="margin:0;font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.01em">GameHub 游戏日报</h1>
  <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:13px">{now} · {source_list}</p>
</div>

<div style="background:#fff;border-radius:12px;padding:24px 28px;box-shadow:0 1px 3px rgba(0,0,0,0.06);border:1px solid #e5e7eb;line-height:1.8">
{body}
</div>

<div style="text-align:center;margin-top:20px;color:#9ca3af;font-size:12px;line-height:1.6">
  GameHub Daily Digest · {len(stats)} 个信源聚合 ·
  <a href="https://github.com/zhuobichen/GameHub" style="color:#4f46e5">GitHub</a>
</div>
</div></body></html>"""


def send_email(html_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎮 GameHub 游戏日报 - {datetime.now().strftime('%m/%d')}"
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_TO
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, timeout=15) as s:
            s.login(EMAIL_USER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())
        print(f"[OK] Email sent to {EMAIL_TO}")
        return True
    except Exception as e:
        print(f"[FAIL] Email: {e}")
        return False


# ═══════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════
async def main():
    print("🎮 GameHub 每日游戏资讯")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   信源: B站(4区) + 小黑盒 + 游研社 + 机核 + 7个海外RSS")
    print()

    # ── Parallel fetch ALL sources ──
    print("📡 并行抓取所有信源...")

    # Schedule all concurrent tasks
    rss_tasks = {name: fetch_rss(name, url) for name, url in RSS_FEEDS}
    api_tasks = {
        "B站(4区)": fetch_bilibili_all(),
        "小黑盒": fetch_xiaoheihe(),
    }

    # Run all in parallel
    all_futures = {}
    for name, coro in {**rss_tasks, **api_tasks}.items():
        all_futures[name] = asyncio.ensure_future(coro)

    # Optional Steam
    steam_games = await fetch_steam_library()
    steam_task = None
    if steam_games:
        print(f"   🎮 Steam 库: {len(steam_games)} 款游戏")
        steam_task = asyncio.ensure_future(fetch_steam_news(steam_games))
        all_futures["Steam"] = steam_task
    else:
        print("   ⚠️ Steam: 未配置 API Key（跳过）")

    # Collect results
    all_items, stats = [], {}
    for name, future in all_futures.items():
        items = await future
        stats[name] = len(items)
        icon = "✅" if items else "⚠️"
        print(f"   {icon} {name}: {len(items)} 条")
        all_items.extend(items)

    total = len(all_items)
    active = sum(1 for v in stats.values() if v > 0)
    print(f"\n📦 总计: {total} 条 | {active} 个活跃信源\n")

    if total < 5:
        print("❌ 资讯太少，跳过生成")
        return

    # AI Digest
    print("🤖 DeepSeek AI 精选消化中...")
    digest = ai_digest(all_items)
    print("   ✅ AI 日报生成完成\n")

    # Email
    print("📧 生成 HTML 邮件...")
    html = build_html(digest, stats)
    send_email(html)

    # Cache
    f = CACHE_DIR / f"digest_{datetime.now().strftime('%Y%m%d')}.md"
    f.write_text(digest, encoding="utf-8")
    print(f"💾 已缓存: {f}")
    print(f"\n✅ 完成! {total} 条 → {active} 信源 → 📧 {EMAIL_TO}")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    asyncio.run(main())
