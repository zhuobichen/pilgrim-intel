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

    async def run(self) -> DigestResult:
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

        # 5. Push
        if self.feed.push_email:
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
    print("\nAll feeds done.")
