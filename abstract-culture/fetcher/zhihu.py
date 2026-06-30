"""知乎热榜抓取器"""
import json, re
from typing import List, Dict, Any
from .base import BaseFetcher


class ZhihuFetcher(BaseFetcher):
    """知乎热榜抓取器"""

    async def fetch(self) -> List[Dict[str, Any]]:
        # 方案A：知乎热榜 HTML 页面（无需登录，提取 initialData）
        try:
            url = 'https://www.zhihu.com/hot'
            headers = self._get_headers()
            headers['Accept'] = 'text/html'
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    m = re.search(r'<script id="js-initialData" type="text/json">(.+?)</script>', text)
                    if m:
                        data = json.loads(m.group(1))
                        hot_list = data.get('initialState', {}).get('topstory', {}).get('hotList', [])
                        items = []
                        for item in hot_list:
                            target = item.get('target', {})
                            if isinstance(target, dict):
                                items.append({
                                    'title': target.get('titleArea', {}).get('text', target.get('title', '')),
                                    'url': target.get('link', {}).get('url', target.get('url', '')),
                                    'heat': item.get('metricsArea', {}).get('text', ''),
                                    'source': '知乎'
                                })
                        if items:
                            return self._clean_items(items[:15])
        except Exception:
            pass

        # 方案B：尝试知乎 RSS（内容可能有限）
        try:
            url = 'https://www.zhihu.com/rss'
            headers = self._get_headers()
            headers['Accept'] = 'application/xml'
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    items = []
                    for m in re.finditer(r'<title>(?!知乎)(.+?)</title>', text):
                        items.append({'title': m.group(1).strip(), 'url': '', 'heat': '', 'source': '知乎'})
                    if items:
                        return self._clean_items(items[:15])
        except Exception:
            pass
        return []
