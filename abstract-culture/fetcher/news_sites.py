"""多源新闻抓取器 - 今日头条 / 36氪 / 澎湃 / 华尔街见闻 / IT之家 / 少数派 / Hacker News"""
import json, re
from typing import List, Dict, Any
from .base import BaseFetcher


class ToutiaoFetcher(BaseFetcher):
    """今日头条热榜"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc'
            headers = self._get_headers()
            headers['Referer'] = 'https://www.toutiao.com/'
            async with self.session.get(url, headers=headers) as resp:
                text = await resp.text()
                # Extract all Title and HotValue pairs
                titles = re.findall(r'"Title":"([^"]*)"', text)
                hots = re.findall(r'"HotValue":(\d+)', text)
                urls = re.findall(r'"Url":"([^"]*)"', text)
                items = []
                for i in range(min(len(titles), 20)):
                    if titles[i]:
                        items.append({
                            'title': titles[i],
                            'url': urls[i] if i < len(urls) else '',
                            'heat': hots[i] if i < len(hots) else '',
                            'source': '今日头条'
                        })
                return self._clean_items(items)
        except Exception as e:
            print(f"今日头条: {type(e).__name__}")
        return []


class Kr36Fetcher(BaseFetcher):
    """36氪快讯"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://36kr.com/api/newsflash'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                news = data.get('data', {}).get('items', [])
                items = [{'title': n.get('title', '').strip(), 'url': n.get('news_url', ''),
                          'heat': '', 'source': '36氪'} for n in news[:20] if n.get('title')]
                return self._clean_items(items)
        except Exception as e:
            print(f"36氪: {type(e).__name__}")
        return []


class ThePaperFetcher(BaseFetcher):
    """澎湃新闻热榜"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                hot = data.get('data', {}).get('hotNews', [])
                items = [{'title': h.get('name', ''), 'url': f"https://www.thepaper.cn/newsDetail_forward_{h.get('contId','')}",
                          'heat': '', 'source': '澎湃'} for h in hot[:20] if h.get('name')]
                return self._clean_items(items)
        except Exception as e:
            print(f"澎湃: {type(e).__name__}")
        return []


class WallStreetCNFetcher(BaseFetcher):
    """华尔街见闻"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=20'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                lives = data.get('data', {}).get('items', [])
                items = [{'title': l.get('title', l.get('content_text', '')), 'url': l.get('uri', ''),
                          'heat': '', 'source': '华尔街见闻'} for l in lives[:20] if l.get('title') or l.get('content_text')]
                return self._clean_items(items)
        except Exception as e:
            print(f"华尔街见闻: {type(e).__name__}")
        return []


class ITHomeFetcher(BaseFetcher):
    """IT之家"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://www.ithome.com/rss/'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                text = await resp.text()
                items = []
                for m in re.finditer(r'<item>.*?<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>.*?<link>(.+?)</link>', text, re.DOTALL):
                    items.append({'title': m.group(1).strip(), 'url': m.group(2).strip(),
                                  'heat': '', 'source': 'IT之家'})
                if not items:
                    # fallback: simpler pattern
                    titles = re.findall(r'<item>\s*<title>(.+?)</title>', text)
                    for t in titles[:15]:
                        t_clean = re.sub(r'<!\[CDATA\[|\]\]>', '', t).strip()
                        if t_clean:
                            items.append({'title': t_clean, 'url': '', 'heat': '', 'source': 'IT之家'})
                return self._clean_items(items[:15])
        except Exception as e:
            print(f"IT之家: {type(e).__name__}")
        return []


class SSPaiFetcher(BaseFetcher):
    """少数派"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://sspai.com/api/v1/article/tag/page/get?tag=%E7%83%AD%E9%97%A8%E6%96%87%E7%AB%A0&limit=15'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                articles = data.get('data', [])
                items = [{'title': a.get('title', ''), 'url': f"https://sspai.com/post/{a.get('id','')}",
                          'heat': '', 'source': '少数派'} for a in articles[:15] if a.get('title')]
                return self._clean_items(items)
        except Exception as e:
            print(f"少数派: {type(e).__name__}")
        return []


class HackerNewsFetcher(BaseFetcher):
    """Hacker News"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=20'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                hits = data.get('hits', [])
                items = [{'title': h.get('title', '').strip(), 'url': h.get('url', f"https://news.ycombinator.com/item?id={h.get('objectID','')}"),
                          'heat': f"↑{h.get('points',0)}", 'source': 'HackerNews'} for h in hits[:20] if h.get('title')]
                return self._clean_items(items)
        except Exception as e:
            print(f"HackerNews: {type(e).__name__}")
        return []
