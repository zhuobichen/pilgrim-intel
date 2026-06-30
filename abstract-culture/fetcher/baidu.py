"""百度热搜抓取器"""
import json, re
from typing import List, Dict, Any
from .base import BaseFetcher


class BaiduHotFetcher(BaseFetcher):
    """百度热搜抓取器"""

    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://top.baidu.com/board?tab=realtime'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                text = await resp.text()
                m = re.search(r'<!--s-data:(.+?)-->', text, re.DOTALL)
                if not m:
                    return []
                data = json.loads(m.group(1))
                cards = data.get('data', {}).get('cards', [])
                # cards is [{component: 'hotList', content: [...]}]
                all_content = []
                for card in cards:
                    all_content.extend(card.get('content', []))
                items = []
                for c in all_content[:25]:
                    items.append({
                        'title': c.get('word', c.get('query', '')),
                        'url': c.get('url', ''),
                        'heat': c.get('hotScore', ''),
                        'source': '百度热搜'
                    })
                return self._clean_items(items)
        except Exception as e:
            print(f"百度热搜: {type(e).__name__}")
        return []
