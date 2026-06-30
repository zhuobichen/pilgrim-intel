"""B站热搜抓取器"""
from typing import List, Dict, Any
from .base import BaseFetcher


class BilibiliFetcher(BaseFetcher):
    """B站热搜抓取器"""

    async def fetch(self) -> List[Dict[str, Any]]:
        """获取B站热搜"""
        try:
            url = 'https://api.bilibili.com/x/web-interface/search/square?limit=30'
            headers = self._get_headers()
            headers['Referer'] = 'https://search.bilibili.com/'

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    items = []
                    for item in data.get('data', {}).get('trending', {}).get('list', []):
                        items.append({
                            'title': item.get('keyword', ''),
                            'url': f"https://search.bilibili.com/all?keyword={item.get('keyword', '')}",
                            'heat': item.get('heat', ''),
                            'source': 'B站'
                        })
                    return self._clean_items(items[:15])
        except Exception as e:
            print(f"获取B站热搜失败: {e}")
        return []
