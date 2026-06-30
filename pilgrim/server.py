#!/usr/bin/env python3
"""Pilgrim Intel — Combined HTTP Feedback + MCP Server.

Starts a single server on port 9876 that handles:
  - /rate       → feedback collection (👍/👎)
  - /stats      → simple HTML stats dashboard
  - /mcp/*      → MCP protocol (JSON-RPC over HTTP)

Usage:
  python pilgrim/server.py [--port 9876]
"""
import argparse
import json
import os
import sys
import textwrap
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pilgrim.storage import PilgrimStore
from pilgrim.models import FeedbackRecord

store = PilgrimStore()


# ═══════════════════════════════════════════════════════
#  HTTP Request Handler
# ═══════════════════════════════════════════════════════

class PilgrimHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    # ── MCP ──────────────────────────────────────────

    def _mcp_discover(self):
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "pilgrim-intel", "version": "2.0.0"},
            "tools": [
                {
                    "name": "pilgrim_search_news",
                    "description": "搜索已收录的新闻内容（全文搜索）",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                            "feed_id": {"type": "string", "description": "可选：限定 feed（abstract-culture/trendradar/gamehub/horizon）"},
                            "since_days": {"type": "integer", "description": "最近几天，默认 7", "default": 7},
                            "limit": {"type": "integer", "description": "返回条数，默认 20", "default": 20}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "pilgrim_get_digest",
                    "description": "获取指定日期的 AI 日报内容",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "feed_id": {"type": "string", "description": "feed ID"},
                            "date": {"type": "string", "description": "日期 YYYY-MM-DD，默认今天"}
                        },
                        "required": ["feed_id"]
                    }
                },
                {
                    "name": "pilgrim_list_sources",
                    "description": "列出所有已配置的信源及其状态",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "pilgrim_get_stats",
                    "description": "获取新闻聚合统计概览",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "period": {"type": "string", "description": "daily/weekly/monthly/all", "default": "weekly"}
                        }
                    }
                },
                {
                    "name": "pilgrim_get_trending",
                    "description": "获取当前最热的新闻（按收录时间）",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "feed_id": {"type": "string", "description": "可选"},
                            "limit": {"type": "integer", "description": "默认 20", "default": 20}
                        }
                    }
                }
            ]
        }

    def _handle_mcp(self, body):
        """Handle JSON-RPC MCP request."""
        try:
            req = json.loads(body)
            rid = req.get("id")
            method = req.get("method", "")
            params = req.get("params", {})
            arguments = params.get("arguments", {})

            if method == "tools/list":
                result = self._mcp_discover()
            elif method == "tools/call":
                result = self._call_tool(params.get("name", ""), arguments)
            elif method == "initialize":
                result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "pilgrim-intel", "version": "2.0.0"}}
            elif method == "notifications/initialized":
                return 200, b"{}"
            else:
                result = {"error": f"Unknown method: {method}"}

            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
            return 200, json.dumps(resp, ensure_ascii=False).encode()
        except Exception as e:
            return 500, json.dumps({"jsonrpc": "2.0", "error": str(e)}).encode()

    def _call_tool(self, name: str, args: dict):
        try:
            if name == "pilgrim_search_news":
                return {
                    "content": [{"type": "text", "text": json.dumps(
                        store.search(args.get("query", ""), args.get("limit", 20),
                                     args.get("feed_id"), args.get("since_days", 7)),
                        ensure_ascii=False, indent=2)
                    }]
                }
            elif name == "pilgrim_get_digest":
                digest = store.get_daily_digest(args.get("feed_id", ""), args.get("date"))
                return {"content": [{"type": "text", "text": digest or "无日报内容"}]}
            elif name == "pilgrim_list_sources":
                from pilgrim.config import get_config
                cfg = get_config()
                sources = []
                for f in cfg.enabled_feeds():
                    sources.append({
                        "feed": f.id, "name": f.name,
                        "sources": [{"id": s.id, "name": s.name, "type": s.type, "enabled": s.enabled} for s in f.sources if s.enabled]
                    })
                return {"content": [{"type": "text", "text": json.dumps(sources, ensure_ascii=False, indent=2)}]}
            elif name == "pilgrim_get_stats":
                return {"content": [{"type": "text", "text": json.dumps(
                    store.get_stats(args.get("period", "weekly")), ensure_ascii=False, indent=2)}]}
            elif name == "pilgrim_get_trending":
                items = store.get_recent(args.get("feed_id"), args.get("limit", 20))
                return {"content": [{"type": "text", "text": json.dumps(items, ensure_ascii=False, indent=2)}]}
            else:
                return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    # ── Routing ─────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/rate":
            self._handle_feedback(qs)
        elif path == "/stats":
            self._handle_stats_page()
        elif path.startswith("/mcp"):
            # MCP over HTTP GET — treat as discover
            code, body = self._handle_mcp(b'{"method":"tools/list","id":1}')
            self._json_response(code, body)
        elif path == "/health":
            self._json_response(200, b'{"status":"ok"}')
        else:
            self._html_response(200, "<h1>Pilgrim Intel 🕊️</h1><p>MCP + Feedback server running on port 9876</p>")

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else "{}"

        if parsed.path.startswith("/mcp"):
            code, resp_body = self._handle_mcp(body)
            self._json_response(code, resp_body)
        else:
            self._json_response(404, b'{"error":"not found"}')

    # ── Feedback ─────────────────────────────────────

    def _handle_feedback(self, qs):
        fp = qs.get("fp", [""])[0]
        rating = int(qs.get("r", ["0"])[0])
        feed_id = qs.get("f", [""])[0]
        source = qs.get("s", [""])[0]
        action = "click_good" if rating >= 4 else "click_bad"

        fb = FeedbackRecord(content_hash=fp, rating=rating, action=action, feed_id=feed_id, source=source)
        store.record_feedback(fb)

        msg = "感谢反馈！👍" if rating >= 4 else "已记录，会优化 👎"
        self._html_response(200, f"<html><body style='text-align:center;padding:40px;font-family:sans-serif'><h2>{msg}</h2><script>setTimeout(function(){{window.close()}},1500)</script></body></html>")

    def _handle_stats_page(self):
        stats = store.get_stats("weekly")
        fb = store.get_feedback_stats()
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Pilgrim Stats</title>
<style>
body{{font-family:-apple-system,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;color:#333;line-height:1.7}}
h1{{color:#0f3460}}
.card{{background:#f8f9fa;border-radius:8px;padding:20px;margin:16px 0}}
.bar{{background:#0f3460;height:24px;border-radius:12px;transition:width 0.5s;margin:4px 0}}
.label{{display:flex;justify-content:space-between;font-size:14px;margin:4px 0}}
th,td{{text-align:left;padding:8px 12px;border-bottom:1px solid #e0e0e0}}
</style></head><body>
<h1>📊 Pilgrim Intel 统计面板</h1>
<p>统计周期: 最近 7 天 · {fb['total']} 条评级 (👍 {fb['good']} / 👎 {fb['bad']})</p>
<div class="card">
<h3>各 Feed 收录量</h3>
{''.join(f'<div class="label"><span>{k}</span><span>{v} 条</span></div><div class="bar" style="width:{min(v/2,100)}%"></div>' for k,v in stats['by_feed'].items())}
</div>
<div class="card">
<h3>Top 信源</h3>
<table><tr><th>信源</th><th>收录</th></tr>
{''.join(f'<tr><td>{r["source"]}</td><td>{r["cnt"]} 条</td></tr>' for r in stats['top_sources'][:10])}
</table></div>
<p style="color:#999;font-size:12px">Powered by Pilgrim Intel 2.0</p>
</body></html>"""
        self._html_response(200, html)

    def _json_response(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())

    def _html_response(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode() if isinstance(html, str) else html)


def main():
    parser = argparse.ArgumentParser(description="Pilgrim Intel MCP + Feedback Server")
    parser.add_argument("--port", type=int, default=9876, help="Server port (default 9876)")
    parser.add_argument("--db", type=str, default=None, help="SQLite database path")
    args = parser.parse_args()

    global store
    store = PilgrimStore(args.db)

    server = HTTPServer(("0.0.0.0", args.port), PilgrimHandler)
    print(f"🕊️  Pilgrim Intel server running on http://localhost:{args.port}")
    print(f"   MCP:  POST http://localhost:{args.port}/mcp")
    print(f"   统计: http://localhost:{args.port}/stats")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        store.close()
        server.shutdown()


if __name__ == "__main__":
    main()
