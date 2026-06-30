"""Reddit 热门抓取器 - 多个抽象/科技/meme子版块"""
from typing import List, Dict, Any
from .base import BaseFetcher


class RedditFetcher(BaseFetcher):
    """Reddit 热门抓取器"""

    SUBREDDITS = [
        ("ProgrammerHumor", "程序员幽默"),
        ("ChatGPT", "ChatGPT"),
        ("memes", "memes"),
        ("Damnthatsinteresting", "有趣发现"),
        ("technology", "科技"),
        ("artificial", "AI"),
        ("science", "科学"),
    ]

    async def fetch(self) -> List[Dict[str, Any]]:
        items = []
        for sub, label in self.SUBREDDITS:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=8"
                headers = self._get_headers()
                async with self.session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    for post in data.get("data", {}).get("children", []):
                        d = post["data"]
                        if d.get("stickied"):
                            continue
                        items.append({
                            "title": d["title"],
                            "url": f"https://reddit.com{d['permalink']}",
                            "score": d.get("score", 0),
                            "comments": d.get("num_comments", 0),
                            "source": f"Reddit r/{sub}",
                        })
            except Exception:
                continue
        items.sort(key=lambda x: x["score"], reverse=True)
        return items[:30]
