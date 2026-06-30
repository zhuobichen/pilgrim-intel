#!/usr/bin/env python3
"""Pilgrim Intel — Unified Runner.

Usage:
  python run.py                          # run all enabled feeds
  python run.py --feed abstract-culture  # run single feed
  python run.py --serve                  # start MCP + feedback server
  python run.py --search "AI 新闻"       # search stored content
  python run.py --stats                  # show stats
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Load .env
env_file = HERE / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)


async def cmd_run(args):
    from pilgrim.engine import run_all_feeds, FeedRunner, PilgrimStore
    from pilgrim.config import get_config

    if args.feed:
        cfg = get_config()
        feed = cfg.get_feed(args.feed)
        if not feed:
            print(f"Unknown feed: {args.feed}")
            return
        store = PilgrimStore()
        runner = FeedRunner(feed, store)
        result = await runner.run()
        store.close()
        print(f"\n🏁 {result.feed_id}: {len(result.items)} 新增, {result.duration_seconds:.1f}s")
    else:
        await run_all_feeds()


def cmd_serve(args):
    from pilgrim.server import main as server_main
    import sys as _sys
    _sys.argv = ["server.py", "--port", str(args.port)]
    server_main()


def cmd_search(args):
    from pilgrim.storage import PilgrimStore
    store = PilgrimStore(args.db)
    results = store.search(args.query, args.limit, args.feed, args.days)
    for r in results:
        print(f"\n📌 {r['title']}")
        print(f"   📡 {r['source']} | {r['feed_id']} | {r['fetched_at'][:10]}")
        if r.get("summary"):
            print(f"   💬 {r['summary'][:100]}")
        print(f"   🔗 {r['url']}")
    store.close()
    print(f"\n✅ 找到 {len(results)} 条结果")


def cmd_stats(args):
    from pilgrim.storage import PilgrimStore
    store = PilgrimStore(args.db)
    stats = store.get_stats(args.period)
    fb = store.get_feedback_stats()
    print(f"\n📊 Pilgrim Intel 统计 ({args.period})")
    print(f"{'='*40}")
    print(f"总收录: {stats['total_items']} 条")
    for fid, cnt in stats['by_feed'].items():
        print(f"  {fid}: {cnt} 条")
    print(f"\n用户反馈: {fb['total']} (👍 {fb['good']} / 👎 {fb['bad']})")
    print(f"\nTop 信源:")
    for r in stats['top_sources'][:10]:
        print(f"  {r['source']}: {r['cnt']} 条")
    store.close()


def main():
    parser = argparse.ArgumentParser(description="Pilgrim Intel — AI News Aggregation Pipeline")
    sub = parser.add_subparsers(dest="command", help="Commands")

    # run
    p_run = sub.add_parser("run", help="Run feeds")
    p_run.add_argument("--feed", "-f", type=str, help="Single feed ID to run")
    p_run.add_argument("--config", "-c", type=str, help="Config file path")

    # serve
    p_serve = sub.add_parser("serve", help="Start HTTP server")
    p_serve.add_argument("--port", "-p", type=int, default=9876)

    # search
    p_search = sub.add_parser("search", help="Search stored content")
    p_search.add_argument("query", type=str, help="Search query")
    p_search.add_argument("--feed", "-f", type=str, help="Filter by feed")
    p_search.add_argument("--days", "-d", type=int, default=7)
    p_search.add_argument("--limit", "-l", type=int, default=20)
    p_search.add_argument("--db", type=str, help="DB path")

    # stats
    p_stats = sub.add_parser("stats", help="Show stats")
    p_stats.add_argument("--period", type=str, default="weekly")
    p_stats.add_argument("--db", type=str, help="DB path")

    args = parser.parse_args()

    if not args.command:
        # Default: run all feeds
        asyncio.run(cmd_run(argparse.Namespace(feed=None)))
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "stats":
        cmd_stats(args)


if __name__ == "__main__":
    main()
