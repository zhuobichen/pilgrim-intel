"""Data models for the pilgrim pipeline."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ContentItem:
    """A single news/article item."""
    title: str
    url: str
    source: str                        # e.g. "BBC", "微博", "Eurogamer"
    feed_id: str                       # parent feed: "abstract-culture", "gamehub", etc.
    heat: str = ""                     # score / vote count / popularity
    summary: str = ""                  # AI-generated one-liner
    content_hash: str = ""             # SHA256 of title+url for dedup
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    extra: Dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Stable identity for dedup — title + normalized host."""
        import hashlib, re
        from urllib.parse import urlparse
        host = urlparse(self.url).netloc if self.url else ""
        raw = f"{self.title.strip().lower()}|{host}"
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class DigestResult:
    """Output of a feed run."""
    feed_id: str
    items: List[ContentItem]
    ai_report: str
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0


@dataclass
class FeedbackRecord:
    """User feedback on a news item."""
    content_hash: str
    rating: int                        # 1-5, or 0 for implicit
    action: str                        # "click_good", "click_bad", "read", "save", "dismiss"
    feed_id: str
    source: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
