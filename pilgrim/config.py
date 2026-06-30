"""YAML-based configuration loader."""
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

# Try to load yaml, fallback gracefully
try:
    import yaml
except ImportError:
    yaml = None


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "feeds.yaml"


class SourceDef:
    def __init__(self, data: dict):
        self.id: str = data.get("id", "")
        self.name: str = data.get("name", "")
        self.type: str = data.get("type", "rss")  # rss | hotlist | api | custom
        self.url: str = data.get("url", "")
        self.enabled: bool = data.get("enabled", True)
        self.extra: dict = data.get("extra", {})

    def __repr__(self):
        return f"SourceDef({self.id}:{self.type})"


class FeedDef:
    def __init__(self, data: dict):
        self.id: str = data["id"]
        self.name: str = data.get("name", self.id)
        self.description: str = data.get("description", "")
        self.sources: List[SourceDef] = [SourceDef(s) for s in data.get("sources", [])]
        self.llm_model: str = data.get("llm", {}).get("model", "deepseek-chat")
        self.llm_api_key_env: str = data.get("llm", {}).get("api_key_env", "DEEPSEEK_API_KEY")
        self.llm_api_base: str = data.get("llm", {}).get("api_base", "https://api.deepseek.com")
        self.llm_temperature: float = data.get("llm", {}).get("temperature", 0.8)
        self.llm_max_tokens: int = data.get("llm", {}).get("max_tokens", 4000)
        self.push_email: bool = data.get("push", {}).get("email", False)
        self.push_email_to: str = data.get("push", {}).get("email_to", "")
        self.prompt_template: str = data.get("prompt_template", "")
        self.schedule: str = data.get("schedule", "daily 18:30")
        self.enabled: bool = data.get("enabled", True)
        self.lang: str = data.get("lang", "zh")
        # Custom fetcher module (e.g. "abstract_culture.fetcher" for existing code)
        self.legacy_fetcher: str = data.get("legacy_fetcher", "")


class PilgrimConfig:
    def __init__(self, path: str = None):
        if path is None:
            path = str(DEFAULT_CONFIG_PATH)
        self.path = path
        self.data: dict = self._load(path)
        self.feeds: List[FeedDef] = [FeedDef(f) for f in self.data.get("feeds", [])]

    def _load(self, path: str) -> dict:
        if yaml:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        # Fallback: parse minimal structure
        return {"feeds": []}

    def get_feed(self, feed_id: str) -> Optional[FeedDef]:
        for f in self.feeds:
            if f.id == feed_id:
                return f
        return None

    def enabled_feeds(self) -> List[FeedDef]:
        return [f for f in self.feeds if f.enabled]


# Global singleton
_config: Optional[PilgrimConfig] = None


def get_config(path: str = None) -> PilgrimConfig:
    global _config
    if _config is None:
        _config = PilgrimConfig(path)
    return _config
