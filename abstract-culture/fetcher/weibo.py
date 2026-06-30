"""微博热搜抓取器"""
from typing import List, Dict, Any
from .base import BaseFetcher


class WeiboFetcher(BaseFetcher):
    """微博热搜抓取器"""

    async def fetch(self) -> List[Dict[str, Any]]:
        """获取微博热搜"""
        try:
            url = 'https://weibo.com/ajax/side/hotSearch'
            headers = self._get_headers()
            headers['Referer'] = 'https://weibo.com/hot/search'

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    items = []
                    for item in data.get('data', {}).get('realtime', []):
                        # 过滤广告
                        if item.get('is_ad') == 1:
                            continue
                        items.append({
                            'title': item.get('word', ''),
                            'url': f"https://s.weibo.com/weibo?q={item.get('word', '')}",
                            'heat': item.get('raw_hot', ''),
                            'source': '微博'
                        })
                    return self._clean_items(items[:15])
        except Exception as e:
            print(f"获取微博热搜失败: {e}")
        return []
