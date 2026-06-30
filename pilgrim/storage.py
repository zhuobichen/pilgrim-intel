"""SQLite storage with dedup, history, feedback & full-text search."""
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import ContentItem, FeedbackRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    feed_id TEXT NOT NULL,
    heat TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    content_text TEXT DEFAULT '',
    published_at TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    extra_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    rating INTEGER DEFAULT 0,
    action TEXT NOT NULL,
    feed_id TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS feed_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    items_fetched INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    ai_report TEXT DEFAULT '',
    errors TEXT DEFAULT '',
    duration_seconds REAL DEFAULT 0
);

-- FTS5 for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
    title, source, summary, content='content', content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content BEGIN
    INSERT INTO content_fts(rowid, title, source, summary)
    VALUES (new.id, new.title, new.source, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content BEGIN
    INSERT INTO content_fts(content_fts, rowid, title, source, summary)
    VALUES ('delete', old.id, old.title, old.source, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS content_au AFTER UPDATE ON content BEGIN
    INSERT INTO content_fts(content_fts, rowid, title, source, summary)
    VALUES ('delete', old.id, old.title, old.source, old.summary);
    INSERT INTO content_fts(rowid, title, source, summary)
    VALUES (new.id, new.title, new.source, new.summary);
END;

CREATE INDEX IF NOT EXISTS idx_content_feed ON content(feed_id);
CREATE INDEX IF NOT EXISTS idx_content_source ON content(source);
CREATE INDEX IF NOT EXISTS idx_content_fetched ON content(fetched_at);
CREATE INDEX IF NOT EXISTS idx_feedback_fingerprint ON feedback(fingerprint);
CREATE INDEX IF NOT EXISTS idx_feedback_feed ON feedback(feed_id);
CREATE INDEX IF NOT EXISTS idx_feed_runs_feed ON feed_runs(feed_id);
"""


class PilgrimStore:
    """Unified SQLite store for all pilgrim feeds."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent / "data" / "pilgrim.db")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ── Content CRUD ──────────────────────────────────────

    def upsert_content(self, item: ContentItem) -> bool:
        """Insert item if new fingerprint. Returns True if actually inserted."""
        fp = item.fingerprint()
        extra = item.extra or {}
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO content
                   (fingerprint, title, url, source, feed_id, heat, summary,
                    published_at, fetched_at, extra_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (fp, item.title, item.url, item.source, item.feed_id,
                 item.heat, item.summary, item.published_at, item.fetched_at,
                 __import__('json').dumps(extra, ensure_ascii=False))
            )
            self.conn.commit()
            return self.conn.total_changes > 0
        except Exception:
            return False

    def upsert_many(self, items: List[ContentItem]) -> int:
        """Bulk upsert. Returns count of newly inserted."""
        import json as _json
        count = 0
        for item in items:
            fp = item.fingerprint()
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO content
                       (fingerprint, title, url, source, feed_id, heat, summary,
                        published_at, fetched_at, extra_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (fp, item.title, item.url, item.source, item.feed_id,
                     item.heat, item.summary, item.published_at, item.fetched_at,
                     _json.dumps(item.extra or {}, ensure_ascii=False))
                )
                if self.conn.total_changes > 0:
                    count += 1
            except Exception:
                continue
        self.conn.commit()
        return count

    def is_duplicate(self, item: ContentItem) -> bool:
        fp = item.fingerprint()
        row = self.conn.execute("SELECT 1 FROM content WHERE fingerprint=?", (fp,)).fetchone()
        return row is not None

    def filter_new(self, items: List[ContentItem]) -> List[ContentItem]:
        """Return only items whose fingerprints are not already in DB."""
        if not items:
            return []
        fps = [item.fingerprint() for item in items]
        placeholders = ','.join(['?'] * len(fps))
        existing = set()
        try:
            rows = self.conn.execute(
                f"SELECT fingerprint FROM content WHERE fingerprint IN ({placeholders})", fps
            ).fetchall()
            existing = {r[0] for r in rows}
        except Exception:
            pass
        return [item for item in items if item.fingerprint() not in existing]

    def search(self, query: str, limit: int = 20, feed_id: str = None,
               since_days: int = 7) -> List[Dict]:
        """Full-text search across all stored content."""
        params = []
        sql = """SELECT c.title, c.url, c.source, c.feed_id, c.summary, c.fetched_at
                 FROM content_fts fts JOIN content c ON fts.rowid = c.id
                 WHERE content_fts MATCH ?"""
        params.append(query)
        if feed_id:
            sql += " AND c.feed_id = ?"
            params.append(feed_id)
        if since_days:
            since = (datetime.now() - timedelta(days=since_days)).isoformat()
            sql += " AND c.fetched_at >= ?"
            params.append(since)
        sql += " ORDER BY c.fetched_at DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_recent(self, feed_id: str = None, limit: int = 50) -> List[Dict]:
        sql = "SELECT * FROM content"
        params = []
        if feed_id:
            sql += " WHERE feed_id = ?"
            params.append(feed_id)
        sql += " ORDER BY fetched_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def get_daily_digest(self, feed_id: str, date: str = None) -> Optional[str]:
        """Get the AI report from the latest feed run."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        row = self.conn.execute(
            """SELECT ai_report FROM feed_runs
               WHERE feed_id=? AND started_at LIKE ?
               ORDER BY started_at DESC LIMIT 1""",
            (feed_id, f"{date}%")
        ).fetchone()
        return row["ai_report"] if row else None

    def get_stats(self, period: str = "weekly") -> Dict:
        """Get feed stats for dashboard."""
        since_map = {"daily": 1, "weekly": 7, "monthly": 30, "all": 3650}
        days = since_map.get(period, 7)
        since = (datetime.now() - timedelta(days=days)).isoformat()

        total = self.conn.execute(
            "SELECT feed_id, COUNT(*) as cnt FROM content WHERE fetched_at >= ? GROUP BY feed_id", (since,)
        ).fetchall()
        top_sources = self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM content WHERE fetched_at >= ? GROUP BY source ORDER BY cnt DESC LIMIT 15", (since,)
        ).fetchall()
        feedback_count = self.conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE created_at >= ?", (since,)
        ).fetchone()[0]

        return {
            "period": period,
            "since": since,
            "total_items": sum(r["cnt"] for r in total),
            "by_feed": {r["feed_id"]: r["cnt"] for r in total},
            "top_sources": [dict(r) for r in top_sources],
            "feedback_count": feedback_count
        }

    # ── Feedback ──────────────────────────────────────────

    def record_feedback(self, fb: FeedbackRecord) -> None:
        self.conn.execute(
            """INSERT INTO feedback (fingerprint, rating, action, feed_id, source, created_at)
               VALUES (?,?,?,?,?,?)""",
            (fb.content_hash, fb.rating, fb.action, fb.feed_id, fb.source, fb.created_at)
        )
        self.conn.commit()

    def get_feedback_stats(self) -> Dict:
        good = self.conn.execute("SELECT COUNT(*) FROM feedback WHERE rating >= 4").fetchone()[0]
        bad = self.conn.execute("SELECT COUNT(*) FROM feedback WHERE rating <= 2").fetchone()[0]
        return {"good": good, "bad": bad, "total": good + bad}

    # ── Feed Run Log ──────────────────────────────────────

    def start_run(self, feed_id: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO feed_runs (feed_id, started_at) VALUES (?,?)",
            (feed_id, datetime.now().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, items_fetched: int, items_new: int,
                   ai_report: str = "", errors: str = "", duration: float = 0):
        self.conn.execute(
            """UPDATE feed_runs SET completed_at=?, items_fetched=?, items_new=?,
               ai_report=?, errors=?, duration_seconds=? WHERE id=?""",
            (datetime.now().isoformat(), items_fetched, items_new,
             ai_report, errors, duration, run_id)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
