"""抖音热搜抓取器"""
from typing import List, Dict, Any
from .base import BaseFetcher


class DouyinFetcher(BaseFetcher):
    """抖音热搜抓取器"""

    async def fetch(self) -> List[Dict[str, Any]]:
        """获取抖音热搜"""
        try:
            url = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'
            headers = self._get_headers()
            headers['Referer'] = 'https://www.douyin.com/'

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    items = []
                    for item in data.get('data', {}).get('word_list', []):
                        items.append({
                            'title': item.get('word', ''),
                            'url': f"https://www.douyin.com/search/{item.get('word', '')}",
                            'heat': item.get('hot_value', ''),
                            'source': '抖音'
                        })
                    return self._clean_items(items[:15])
        except Exception as e:
            print(f"获取抖音热搜失败: {e}")
        return []
