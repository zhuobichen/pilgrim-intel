"""Unified pipeline engine: fetch -> dedup -> AI -> push."""
import asyncio
import json
import os
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Optional

import httpx

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from .config import FeedDef, get_config
from .models import ContentItem, DigestResult
from .storage import PilgrimStore

HERE = Path(__file__).resolve().parent.parent
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Encoding-safe print/log wrapper
def _safe(msg: str) -> str:
    return msg.encode('gbk', errors='replace').decode('gbk', errors='replace')

def _safe_print(msg: str):
    """Print safely on Windows GBK terminals."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


class FeedRunner:
    """Runs one feed end-to-end: fetch sources -> dedup -> AI digest -> push."""

    def __init__(self, feed: FeedDef, store: PilgrimStore = None):
        self.feed = feed
        self.store = store or PilgrimStore()
        ai_key = os.getenv(feed.llm_api_key_env, "")
        self.ai = None
        if ai_key and OpenAI:
            try:
                self.ai = OpenAI(api_key=ai_key, base_url=feed.llm_api_base)
            except Exception as e:
                self.log(f"OpenAI init failed: {e}")
        self.log_path = LOG_DIR / f"{feed.id}.log"

    def log(self, msg: str):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] {msg}"
        try:
            print(line.encode('utf-8', errors='replace').decode('utf-8'))
        except Exception:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _build_rating_links(self, fp: str, feed_id: str, source: str) -> str:
        return (
            f'<a href="http://localhost:9876/rate?fp={fp}&r=5&f={feed_id}&s={source}" '
            f'style="text-decoration:none;margin:0 4px">[like]</a>'
            f'<a href="http://localhost:9876/rate?fp={fp}&r=1&f={feed_id}&s={source}" '
            f'style="text-decoration:none;margin:0 4px">[dislike]</a>'
        )

    # --- Source Fetching ---

    async def _fetch_rss(self, src) -> List[ContentItem]:
        import xml.etree.ElementTree as ET
        items = []
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                         headers={"User-Agent": "PilgrimIntel/2.0"}) as c:
                r = await c.get(src.url)
                if r.status_code != 200:
                    return items
                root = ET.fromstring(r.text)
                for el in root.iter("item"):
                    t = el.findtext("title", "").strip()
                    lnk_el = el.find("link")
                    link = el.findtext("link", "").strip()
                    if not link and lnk_el is not None:
                        link = lnk_el.get("href", "")
                    if t and len(t) > 3:
                        items.append(ContentItem(title=t, url=link, source=src.name,
                                                 feed_id=self.feed.id))
                # Atom
                atom_ns = "http://www.w3.org/2005/Atom"
                for entry in root.iter(f"{{{atom_ns}}}entry"):
                    t = entry.findtext(f"{{{atom_ns}}}title", "").strip()
                    lnk_el = entry.find(f"{{{atom_ns}}}link")
                    href = lnk_el.get("href", "") if lnk_el is not None else ""
                    if t and len(t) > 3:
                        items.append(ContentItem(title=t, url=href, source=src.name,
                                                 feed_id=self.feed.id))
        except Exception as e:
            self.log(f"RSS {src.name}: {type(e).__name__}")
        return items[:20]

    async def _fetch_json(self, src) -> List[ContentItem]:
        items = []
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                         headers={"User-Agent": "Mozilla/5.0"}) as c:
                r = await c.get(src.url)
                if r.status_code != 200:
                    return items
                data = r.json()
                entries = []
                if isinstance(data, dict):
                    for key in ("data", "items", "list", "result", "hot", "articles", "hits", "posts"):
                        val = data.get(key)
                        if isinstance(val, list):
                            entries = val; break
                        if isinstance(val, dict):
                            inner = val.get("items") or val.get("articles") or val.get("list") or []
                            if isinstance(inner, list):
                                entries = inner; break
                elif isinstance(data, list):
                    entries = data
                for entry in entries[:20]:
                    title = entry.get("title") or entry.get("name") or entry.get("word") or entry.get("headline")
                    if not title and isinstance(entry.get("title"), dict):
                        title = entry["title"].get("rendered") or ""
                    url = entry.get("url") or entry.get("link") or entry.get("href") or entry.get("uri") or ""
                    heat = entry.get("heat") or entry.get("hotValue") or entry.get("score") or entry.get("points") or entry.get("votes_count") or ""
                    if title:
                        items.append(ContentItem(title=str(title), url=str(url), source=src.name,
                                                 feed_id=self.feed.id, heat=str(heat)))
        except Exception as e:
            self.log(f"JSON {src.name}: {type(e).__name__}")
        return items

    async def fetch_source(self, src) -> List[ContentItem]:
        if src.type == "rss":
            return await self._fetch_rss(src)
        elif src.type in ("hotlist", "api"):
            return await self._fetch_json(src)
        return []

    async def fetch_all_sources(self) -> List[ContentItem]:
        tasks = [self.fetch_source(s) for s in self.feed.sources if s.enabled]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_items = []
        for i, r in enumerate(results):
            src_name = self.feed.sources[i].name
            if isinstance(r, Exception):
                self.log(f"Source {src_name}: {r}")
            elif r:
                all_items.extend(r)
                self.log(f"  OK {src_name}: {len(r)} items")
        return all_items

    # --- AI Digest ---

    def generate_digest(self, items: List[ContentItem]) -> str:
        if not self.ai or not self.feed.prompt_template:
            return self._fallback_digest(items)

        context_lines = []
        for i, item in enumerate(items[:60], 1):
            context_lines.append(f"{i}. [{item.source}] {item.title}")
            if item.summary:
                context_lines.append(f"   > {item.summary[:100]}")

        prompt = self.feed.prompt_template.replace("{{CONTEXT}}", "\n".join(context_lines))
        prompt = prompt.replace("{{DATE}}", datetime.now().strftime('%Y-%m-%d'))
        prompt = prompt.replace("{{COUNT}}", str(len(items)))

        try:
            resp = self.ai.chat.completions.create(
                model=self.feed.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.feed.llm_temperature,
                max_tokens=self.feed.llm_max_tokens
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            self.log(f"AI failed: {e}")
            return self._fallback_digest(items)

    def _fallback_digest(self, items: List[ContentItem]) -> str:
        lines = [f"# {self.feed.name}\n", f"Total {len(items)} items\n"]
        for item in items[:30]:
            lines.append(f"- [{item.source}] {item.title}")
        return "\n".join(lines)

    # --- Push ---

    def push_email(self, subject: str, html_body: str):
        to_addr = self.feed.push_email_to or os.getenv("EMAIL_TO", "")
        if not to_addr:
            self.log("No EMAIL_TO configured, skip email push")
            return
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = os.getenv("EMAIL_USER", "")
            msg["To"] = to_addr
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP_SSL(os.getenv("EMAIL_HOST", "smtp.qq.com"),
                                  int(os.getenv("EMAIL_PORT", "465"))) as s:
                s.login(os.getenv("EMAIL_USER", ""), os.getenv("EMAIL_PASSWORD", ""))
                s.sendmail(msg["From"], [to_addr], msg.as_string())
            self.log(f"Email sent to {to_addr}")
        except Exception as e:
            self.log(f"Email failed: {e}")

    # --- Main Run ---

    async def run(self, skip_push: bool = False) -> DigestResult:
        """Run one feed end-to-end.

        Args:
            skip_push: 如果为 True，则跳过邮件推送（用于合并推送场景，
                       由调用方统一收集各 feed 结果后发送单封邮件）。
        """
        start = time.time()
        errors = []
        self.log(f"{'='*50}")
        self.log(f"START {self.feed.name}")

        run_id = self.store.start_run(self.feed.id)

        # 1. Fetch
        all_items = await self.fetch_all_sources()
        self.log(f"Fetched: {len(all_items)} items")

        # 2. Dedup
        new_items = self.store.filter_new(all_items)
        self.log(f"New: {len(new_items)} / Total: {len(all_items)}")

        # 3. Store
        stored = self.store.upsert_many(new_items) if new_items else 0
        self.log(f"Stored: {stored} items")

        # 4. AI Digest
        digest_target = new_items if new_items else all_items[:30]
        ai_report = ""
        if self.ai and self.feed.prompt_template:
            self.log("AI digest generating...")
            ai_report = self.generate_digest(digest_target)
        else:
            ai_report = self._fallback_digest(digest_target)

        # 5. Push（合并推送模式下跳过单 feed 邮件）
        if self.feed.push_email and not skip_push:
            html = self._build_html_email(ai_report, digest_target[:30])
            subject = f"{self.feed.name} {datetime.now().strftime('%Y-%m-%d')}"
            self.push_email(subject, html)

        # 6. Done
        duration = time.time() - start
        self.store.finish_run(run_id, len(all_items), stored, ai_report,
                              errors=";".join(errors) if errors else "",
                              duration=duration)
        self.log(f"DONE ({duration:.1f}s)")
        return DigestResult(feed_id=self.feed.id, items=new_items, ai_report=ai_report,
                            errors=errors, duration_seconds=duration)

    def _build_html_email(self, ai_report: str, items: List[ContentItem]) -> str:
        items_html = ""
        for item in items:
            fp = item.fingerprint()
            rating = self._build_rating_links(fp, self.feed.id, item.source)
            items_html += (
                f'<li style="margin:8px 0">'
                f'<a href="{item.url}" style="font-weight:bold;color:#1a73e8">{item.title}</a>'
                f' <span style="color:#888;font-size:12px">[{item.source}]</span>'
                f'<br>{rating}'
                f'</li>'
            )
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:700px;margin:20px auto;padding:0 16px;color:#333;line-height:1.7}}
h1{{color:#1a1a2e;border-bottom:2px solid #0f3460;padding-bottom:10px}}
h2,h3{{color:#16213e}}
a{{color:#1a73e8;text-decoration:none}}
a:hover{{text-decoration:underline}}
.block{{background:#f8f9fa;border-left:4px solid #0f3460;padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0}}
.footer{{margin-top:30px;padding-top:15px;border-top:1px solid #e0e0e0;font-size:12px;color:#999}}
.footer a{{color:#999}}
</style></head><body>
<div class="block"><pre style="white-space:pre-wrap;font-family:inherit;margin:0">{ai_report}</pre></div>
<h3>Today: {len(items)} items</h3>
<ol>{items_html}</ol>
<div class="footer">
<p>Powered by <b>Pilgrim Intel 2.0</b></p>
<p><a href="http://localhost:9876/stats">Stats</a></p>
</div></body></html>"""
        return html


# --- Consolidated HTML Builder ---

# 每个 feed 对应的标签页配色与图标
_FEED_TAB_META = {
    "abstract-culture": {"icon": "🎭", "color": "#7c3aed", "desc": "15+ 平台热点文化分析"},
    "trendradar":       {"icon": "📡", "color": "#0ea5e9", "desc": "热榜 + RSS 新闻简报"},
    "gamehub":          {"icon": "🎮", "color": "#ef4444", "desc": "游戏资讯日报"},
    "horizon":          {"icon": "🛰️", "color": "#10b981", "desc": "科技新闻双语日报"},
}
_DEFAULT_TAB_META = {"icon": "📰", "color": "#0f3460", "desc": ""}


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _markdown_to_html(md: str) -> str:
    """极简 Markdown → HTML 转换（标题/粗体/列表/段落）。
    仅为展示用，不引入外部依赖。
    """
    if not md:
        return ""
    import re as _re
    lines = _escape_html(md).split("\n")
    out = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_lists()
            continue
        # 标题
        m = _re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            close_lists()
            level = min(len(m.group(1)), 4) + 2  # h3-h6，避免与页面主标题冲突
            out.append(f"<h{level} class='digest-h'>{m.group(2)}</h{level}>")
            continue
        # 有序列表
        m = _re.match(r"^\s*(\d+)[.、)]\s+(.*)$", line)
        if m:
            if in_ul:
                out.append("</ul>"); in_ul = False
            if not in_ol:
                out.append("<ol>"); in_ol = True
            out.append(f"<li>{m.group(2)}</li>")
            continue
        # 无序列表
        m = _re.match(r"^\s*[-*•]\s+(.*)$", line)
        if m:
            if in_ol:
                out.append("</ol>"); in_ol = False
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{m.group(1)}</li>")
            continue
        # 普通段落
        close_lists()
        # 行内粗体 **text**
        inline = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        out.append(f"<p>{inline}</p>")
    close_lists()
    return "\n".join(out)


def build_consolidated_html(feed_results) -> str:
    """构建一个带标签页切换的合并 HTML 页面。

    Args:
        feed_results: List[(FeedDef, List[ContentItem], str ai_report)]

    Returns:
        完整的 HTML 字符串
    """
    today = datetime.now().strftime('%Y-%m-%d %A')
    total_items = sum(len(items) for _, items, _ in feed_results)

    # 构建标签按钮与面板
    tabs_html = []
    panels_html = []
    for idx, (feed, items, ai_report) in enumerate(feed_results):
        meta = _FEED_TAB_META.get(feed.id, _DEFAULT_TAB_META)
        active = "active" if idx == 0 else ""
        tabs_html.append(
            f'<button class="tab-btn {active}" data-tab="tab-{idx}" '
            f'style="--tab-color:{meta["color"]}">'
            f'<span class="tab-icon">{meta["icon"]}</span>'
            f'<span class="tab-name">{_escape_html(feed.name)}</span>'
            f'<span class="tab-count">{len(items)}</span>'
            f'</button>'
        )

        # 该 feed 的新闻列表
        items_cards = []
        for item in items[:30]:
            fp = item.fingerprint()
            rating = (
                f'<a href="http://localhost:9876/rate?fp={fp}&r=5&f={feed.id}&s={_escape_html(item.source)}" '
                f'class="rate like" title="赞">👍</a>'
                f'<a href="http://localhost:9876/rate?fp={fp}&r=1&f={feed.id}&s={_escape_html(item.source)}" '
                f'class="rate dislike" title="踩">👎</a>'
            )
            url = item.url or "#"
            heat_badge = (f'<span class="heat">🔥 {_escape_html(item.heat)}</span>'
                          if item.heat else "")
            items_cards.append(
                f'<div class="news-card">'
                f'<a class="news-title" href="{url}" target="_blank" rel="noopener">{_escape_html(item.title)}</a>'
                f'<div class="news-meta">'
                f'<span class="source">{_escape_html(item.source)}</span>'
                f'{heat_badge}'
                f'<span class="rate-group">{rating}</span>'
                f'</div>'
                f'</div>'
            )
        items_section = "".join(items_cards) if items_cards else '<p class="empty">暂无内容</p>'

        digest_html = _markdown_to_html(ai_report)

        panels_html.append(
            f'<section class="tab-panel {active}" id="tab-{idx}">'
            f'<div class="panel-head" style="--accent:{meta["color"]}">'
            f'<div class="panel-title">{meta["icon"]} {_escape_html(feed.name)}</div>'
            f'<div class="panel-desc">{_escape_html(meta["desc"])}</div>'
            f'</div>'
            f'<div class="digest">{digest_html if digest_html else "<p class=\"empty\">暂无摘要</p>"}</div>'
            f'<h3 class="section-title">📋 今日条目（{len(items)}）</h3>'
            f'<div class="news-list">{items_section}</div>'
            f'</section>'
        )

    tabs = "".join(tabs_html)
    panels = "".join(panels_html)

    feed_names = " · ".join(_escape_html(f.name) for f, _, _ in feed_results)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pilgrim Intel 每日情报 · {today}</title>
<style>
:root{{
  --bg:#0f172a; --bg2:#1e293b; --card:#ffffff; --text:#0f172a; --muted:#64748b;
  --border:#e2e8f0; --shadow:0 10px 30px rgba(15,23,42,.08);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);
  min-height:100vh;color:var(--text);line-height:1.7;padding:24px 12px;
}}
.wrap{{max-width:960px;margin:0 auto}}

/* 顶部头图 */
.hero{{
  background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#ec4899 100%);
  border-radius:20px;padding:32px 28px;color:#fff;text-align:center;
  box-shadow:var(--shadow);margin-bottom:20px;position:relative;overflow:hidden;
}}
.hero::before{{
  content:"";position:absolute;inset:0;
  background:radial-gradient(circle at 20% 20%,rgba(255,255,255,.18),transparent 40%),
             radial-gradient(circle at 80% 0%,rgba(255,255,255,.12),transparent 35%);
}}
.hero h1{{position:relative;font-size:28px;font-weight:800;letter-spacing:1px}}
.hero .sub{{position:relative;margin-top:8px;font-size:14px;opacity:.92}}
.hero .stats{{position:relative;margin-top:14px;display:flex;justify-content:center;gap:24px;flex-wrap:wrap}}
.hero .stat{{background:rgba(255,255,255,.18);backdrop-filter:blur(6px);border-radius:12px;padding:8px 18px}}
.hero .stat b{{font-size:20px;display:block}}
.hero .stat span{{font-size:12px;opacity:.9}}

/* 标签栏 */
.tabs{{
  display:flex;gap:8px;background:var(--card);padding:10px;border-radius:16px;
  box-shadow:var(--shadow);margin-bottom:18px;overflow-x:auto;position:sticky;top:8px;z-index:10;
}}
.tab-btn{{
  flex:1;min-width:140px;border:none;background:#f1f5f9;color:var(--muted);
  padding:12px 14px;border-radius:11px;cursor:pointer;font-size:14px;font-weight:600;
  display:flex;align-items:center;justify-content:center;gap:8px;
  transition:all .25s ease;border:2px solid transparent;white-space:nowrap;
}}
.tab-btn:hover{{background:#e2e8f0;transform:translateY(-1px)}}
.tab-btn.active{{background:var(--tab-color);color:#fff;box-shadow:0 6px 16px rgba(0,0,0,.18)}}
.tab-icon{{font-size:18px}}
.tab-count{{background:rgba(0,0,0,.12);border-radius:10px;padding:1px 8px;font-size:12px;font-weight:700}}
.tab-btn.active .tab-count{{background:rgba(255,255,255,.28)}}

/* 面板 */
.tab-panel{{display:none;background:var(--card);border-radius:18px;box-shadow:var(--shadow);
  padding:24px;animation:fade .35s ease}}
.tab-panel.active{{display:block}}
@keyframes fade{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.panel-head{{border-left:5px solid var(--accent);padding:4px 0 4px 14px;margin-bottom:18px}}
.panel-title{{font-size:22px;font-weight:800;color:var(--accent)}}
.panel-desc{{font-size:13px;color:var(--muted);margin-top:2px}}

.digest{{
  background:#f8fafc;border:1px solid var(--border);border-radius:14px;
  padding:18px 20px;margin-bottom:22px;font-size:14.5px;color:#334155;
}}
.digest h3,.digest h4,.digest h5,.digest h6{{color:#0f172a;margin:14px 0 8px;font-weight:700}}
.digest h3{{font-size:17px}}.digest h4{{font-size:16px}}
.digest p{{margin:8px 0}}
.digest ul,.digest ol{{margin:8px 0 8px 22px}}
.digest li{{margin:4px 0}}
.digest strong{{color:#7c3aed}}
.digest:empty{{display:none}}

.section-title{{font-size:16px;font-weight:700;color:#0f172a;margin:6px 0 14px;
  padding-bottom:8px;border-bottom:2px solid var(--border)}}

.news-list{{display:flex;flex-direction:column;gap:10px}}
.news-card{{
  border:1px solid var(--border);border-radius:12px;padding:12px 14px;
  transition:all .2s ease;background:#fff;
}}
.news-card:hover{{border-color:#c7d2fe;box-shadow:0 4px 12px rgba(99,102,241,.12);transform:translateY(-1px)}}
.news-title{{display:block;font-size:15px;font-weight:600;color:#1e293b;text-decoration:none;margin-bottom:6px}}
.news-title:hover{{color:#4f46e5;text-decoration:underline}}
.news-meta{{display:flex;align-items:center;gap:10px;font-size:12px;color:var(--muted);flex-wrap:wrap}}
.source{{background:#eef2ff;color:#4338ca;border-radius:6px;padding:2px 8px;font-weight:600}}
.heat{{color:#ef4444;font-weight:600}}
.rate-group{{margin-left:auto;display:flex;gap:6px}}
.rate{{text-decoration:none;font-size:13px;padding:2px 6px;border-radius:6px;background:#f1f5f9}}
.rate:hover{{background:#e2e8f0}}

.empty{{color:var(--muted);font-style:italic;padding:14px;text-align:center}}

.footer{{
  text-align:center;color:#94a3b8;font-size:12px;margin-top:24px;padding:16px;
}}
.footer a{{color:#94a3b8}}

@media (max-width:640px){{
  .tabs{{flex-wrap:nowrap}}
  .tab-btn{{min-width:120px;font-size:13px}}
  .hero h1{{font-size:22px}}
  .hero .stats{{gap:10px}}
  .hero .stat{{padding:6px 12px}}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>🕊️ Pilgrim Intel 每日情报</h1>
    <div class="sub">{today} · {feed_names}</div>
    <div class="stats">
      <div class="stat"><b>{len(feed_results)}</b><span>分类</span></div>
      <div class="stat"><b>{total_items}</b><span>条目</span></div>
      <div class="stat"><b>{today.split()[0]}</b><span>日期</span></div>
    </div>
  </div>

  <div class="tabs" role="tablist">{tabs}</div>

  {panels}

  <div class="footer">
    <p>Powered by <b>Pilgrim Intel 2.0</b> · DeepSeek AI 摘要 · 一封邮件聚合四类情报</p>
    <p><a href="http://localhost:9876/stats">📊 统计面板</a></p>
  </div>
</div>
<script>
(function(){{
  var btns=document.querySelectorAll('.tab-btn');
  var panels=document.querySelectorAll('.tab-panel');
  btns.forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var id=btn.getAttribute('data-tab');
      btns.forEach(function(b){{b.classList.remove('active')}});
      panels.forEach(function(p){{p.classList.remove('active')}});
      btn.classList.add('active');
      var panel=document.getElementById(id);
      if(panel) panel.classList.add('active');
      try{{localStorage.setItem('pilgrim_active_tab',id)}}catch(e){{}}
    }});
  }});
  // 记忆上次切换的标签
  try{{
    var saved=localStorage.getItem('pilgrim_active_tab');
    if(saved){{
      var sb=document.querySelector('.tab-btn[data-tab="'+saved+'"]');
      if(sb) sb.click();
    }}
  }}catch(e){{}}
}})();
</script>
</body>
</html>"""


def save_consolidated_html_file(html: str) -> str:
    """将合并 HTML 保存到 reports/ 目录，返回文件路径。"""
    reports_dir = HERE / "reports"
    reports_dir.mkdir(exist_ok=True)
    filename = f"pilgrim-digest-{datetime.now().strftime('%Y%m%d-%H%M')}.html"
    path = reports_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return str(path)


def send_consolidated_email(html: str, store_logger=None):
    """发送单封合并邮件（包含所有 feed 的内容）。"""
    to_addr = os.getenv("EMAIL_TO", "")
    if not to_addr:
        msg = "No EMAIL_TO configured, skip consolidated email"
        print(msg)
        if store_logger:
            store_logger.log(msg)
        return
    subject = f"Pilgrim Intel 每日情报 · {datetime.now().strftime('%Y-%m-%d')}"
    try:
        mime = MIMEMultipart("alternative")
        mime["Subject"] = subject
        mime["From"] = os.getenv("EMAIL_USER", "")
        mime["To"] = to_addr
        mime.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL(os.getenv("EMAIL_HOST", "smtp.qq.com"),
                              int(os.getenv("EMAIL_PORT", "465"))) as s:
            s.login(os.getenv("EMAIL_USER", ""), os.getenv("EMAIL_PASSWORD", ""))
            s.sendmail(mime["From"], [to_addr], mime.as_string())
            _safe_print(f"Consolidated email sent to {to_addr}")
    except Exception as e:
            _safe_print(f"Consolidated email failed: {e}")


# --- Batch Runner ---

async def run_all_feeds(config_path: str = None):
    cfg = get_config(config_path)
    store = PilgrimStore()
    for feed in cfg.enabled_feeds():
        runner = FeedRunner(feed, store)
        try:
            await runner.run()
        except Exception as e:
            print(f"ERROR {feed.id}: {e}")
    store.close()
    _safe_print("All feeds done.")


async def run_all_feeds_consolidated(config_path: str = None):
    """运行所有 feed（抓取 + AI 摘要），但只发送【一封】合并邮件，
    并保存一份带标签页切换的 HTML 文件。

    流程：
        1. 逐个 feed 跑 fetch → dedup → store → AI digest（跳过单 feed 邮件）
        2. 收集所有 (feed, items, ai_report)
        3. 构建带 4 个标签页的合并 HTML
        4. 保存 HTML 文件 + 发送单封合并邮件
    """
    cfg = get_config(config_path)
    store = PilgrimStore()

    feed_results = []
    for feed in cfg.enabled_feeds():
        runner = FeedRunner(feed, store)
        try:
            result = await runner.run(skip_push=True)
            # digest_target 与 run() 内部一致：优先用新增，否则用前 30 条
            digest_items = result.items if result.items else []
            feed_results.append((feed, digest_items, result.ai_report))
        except Exception as e:
            print(f"ERROR {feed.id}: {e}")
            feed_results.append((feed, [], f"⚠️ 此分类运行失败: {e}"))

    store.close()

    if not feed_results:
        print("没有可用的 feed，退出。")
        return

    # 构建合并 HTML
    html = build_consolidated_html(feed_results)

    # 保存 HTML 文件
    try:
        html_path = save_consolidated_html_file(html)
        _safe_print(f"HTML saved: {html_path}")
    except Exception as e:
        _safe_print(f"HTML save failed: {e}")

    # 发送单封合并邮件
    send_consolidated_email(html)

    _safe_print("Consolidated push done (1 email + 1 HTML).")
