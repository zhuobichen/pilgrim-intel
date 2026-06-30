"""抓取器基类"""
import asyncio
import random
from typing import List, Dict, Any, Optional
import aiohttp


class BaseFetcher:
    """热点数据抓取器基类"""

    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    def _get_headers(self) -> Dict[str, str]:
        """获取随机请求头"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout, headers=self._get_headers())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch(self) -> List[Dict[str, Any]]:
        """抓取热点数据，子类必须实现"""
        raise NotImplementedError

    def _clean_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """数据清洗：过滤广告、过短标题、去重"""
        # 过滤过短/无意义标题
        items = [item for item in items if len(item.get('title', '').strip()) > 4]

        # 去重
        seen_titles = set()
        unique_items = []
        for item in items:
            title = item['title'].strip()
            if title not in seen_titles:
                seen_titles.add(title)
                unique_items.append(item)

        return unique_items
