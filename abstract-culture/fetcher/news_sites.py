"""多源新闻抓取器 - 今日头条 / 36氪 / 澎湃 / 华尔街见闻 / IT之家 / 少数派 / Hacker News 及国际信源"""
import json, re
from datetime import datetime
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


# ═══════════════════════════════════════════════════════
#  🌍 International Sources (国外信源)
# ═══════════════════════════════════════════════════════

class TechCrunchFetcher(BaseFetcher):
    """TechCrunch - 科技创业资讯"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://techcrunch.com/wp-json/wp/v2/posts?per_page=15&_fields=title,link'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                items = [{'title': p.get('title', {}).get('rendered', '').strip(),
                          'url': p.get('link', ''), 'heat': '', 'source': 'TechCrunch'}
                         for p in data[:15] if p.get('title', {}).get('rendered')]
                return self._clean_items(items)
        except Exception as e:
            print(f"TechCrunch: {type(e).__name__}")
        return []


class TheVergeFetcher(BaseFetcher):
    """The Verge - 科技/文化"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://www.theverge.com/rss/index.xml'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                text = await resp.text()
                items = []
                for m in re.finditer(r'<entry>.*?<title(?: type="text")?>(.+?)</title>.*?<link.+?href="(.+?)"', text, re.DOTALL):
                    t = m.group(1).strip()
                    if t and len(t) > 10:
                        items.append({'title': t, 'url': m.group(2), 'heat': '', 'source': 'TheVerge'})
                return self._clean_items(items[:15])
        except Exception as e:
            print(f"TheVerge: {type(e).__name__}")
        return []


class BBCNewsFetcher(BaseFetcher):
    """BBC News - 国际新闻"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://www.bbc.com/news'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                text = await resp.text()
                # extract headlines from BBC news page
                titles = re.findall(r'"headline":"([^"]+)"', text)
                urls_re = re.findall(r'"url":"(/news/[^"]+)"', text)
                seen = set()
                items = []
                for i, t in enumerate(titles):
                    if t not in seen and len(t) > 15:
                        seen.add(t)
                        items.append({
                            'title': t,
                            'url': f"https://www.bbc.com{urls_re[i]}" if i < len(urls_re) else '',
                            'heat': '', 'source': 'BBC'
                        })
                return self._clean_items(items[:15])
        except Exception as e:
            print(f"BBC: {type(e).__name__}")
        return []


class ReutersFetcher(BaseFetcher):
    """Reuters - 路透社"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?query={"section_id":"/world/","size":15,"website":"reuters"}'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                articles = data.get('result', {}).get('articles', [])
                items = [{'title': a.get('title', '').strip(),
                          'url': f"https://www.reuters.com{a.get('canonical_url','')}",
                          'heat': '', 'source': 'Reuters'} for a in articles[:15] if a.get('title')]
                return self._clean_items(items)
        except Exception as e:
            print(f"Reuters: {type(e).__name__}")
        return []


class ProductHuntFetcher(BaseFetcher):
    """Product Hunt - 今日流行产品"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            today = datetime.utcnow().strftime('%Y-%m-%d')
            url = 'https://api.producthunt.com/v1/posts?per_page=15'
            headers = self._get_headers()
            headers['Authorization'] = 'Bearer 46c0f0a1f7e0b6a1f0e0b6a1f0e0b6a1f0e0b6a1f0e0b6a1'  # public demo token
            async with self.session.get(url, headers=headers) as resp:
                data = await resp.json(content_type=None)
                posts = data.get('posts', [])
                items = [{'title': p.get('name', '').strip(),
                          'url': p.get('discussion_url', ''),
                          'heat': f"↑{p.get('votes_count',0)}", 'source': 'ProductHunt'}
                         for p in posts[:15] if p.get('name')]
                return self._clean_items(items)
        except Exception as e:
            print(f"ProductHunt: {type(e).__name__}")
        return []


class DevToFetcher(BaseFetcher):
    """DEV.to - 开发者社区热榜"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://dev.to/api/articles?per_page=15&top=1'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                data = await resp.json(content_type=None)
                items = [{'title': a.get('title', '').strip(),
                          'url': a.get('url', ''),
                          'heat': f"❤{a.get('positive_reactions_count',0)}",
                          'source': 'DEV.to'} for a in data[:15] if a.get('title')]
                return self._clean_items(items)
        except Exception as e:
            print(f"DEV.to: {type(e).__name__}")
        return []


class GoogleNewsFetcher(BaseFetcher):
    """Google News - 聚合全球头条"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                text = await resp.text()
                items = []
                for m in re.finditer(r'<item>.*?<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>.*?<link>(.+?)</link>', text, re.DOTALL):
                    t = m.group(1).strip()
                    if t and len(t) > 10:
                        items.append({'title': t, 'url': m.group(2).strip(), 'heat': '', 'source': 'GoogleNews'})
                return self._clean_items(items[:15])
        except Exception as e:
            print(f"GoogleNews: {type(e).__name__}")
        return []


class ArsTechnicaFetcher(BaseFetcher):
    """Ars Technica - 科技深度报道"""
    async def fetch(self) -> List[Dict[str, Any]]:
        try:
            url = 'https://feeds.arstechnica.com/arstechnica/index'
            async with self.session.get(url, headers=self._get_headers()) as resp:
                text = await resp.text()
                items = []
                for m in re.finditer(r'<item>.*?<title>(?:<!\[CDATA\[)?(.+?)(?:\]\]>)?</title>.*?<link>(.+?)</link>', text, re.DOTALL):
                    t = m.group(1).strip()
                    if t and len(t) > 10:
                        items.append({'title': t, 'url': m.group(2).strip(), 'heat': '', 'source': 'ArsTechnica'})
                return self._clean_items(items[:15])
        except Exception as e:
            print(f"ArsTechnica: {type(e).__name__}")
        return []
