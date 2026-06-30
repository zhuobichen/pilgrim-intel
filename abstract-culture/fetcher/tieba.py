"""贴吧热帖抓取器"""
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base import BaseFetcher


class TiebaFetcher(BaseFetcher):
    """贴吧热帖抓取器（孙笑川吧）"""

    async def fetch(self) -> List[Dict[str, Any]]:
        """获取贴吧热帖"""
        try:
            url = 'https://tieba.baidu.com/f?kw=%E5%AD%99%E7%AC%91%E5%B7%9D&tab=good'
            headers = self._get_headers()
            headers['Referer'] = 'https://tieba.baidu.com/'

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    items = []

                    # 解析帖子列表
                    threads = soup.find_all('div', class_='threadlist_title')
                    for thread in threads[:15]:
                        a_tag = thread.find('a')
                        if a_tag:
                            title = a_tag.get_text(strip=True)
                            href = a_tag.get('href', '')
                            if href.startswith('/p/'):
                                href = f"https://tieba.baidu.com{href}"
                            items.append({
                                'title': title,
                                'url': href,
                                'heat': '',
                                'source': '贴吧'
                            })

                    return self._clean_items(items)
        except Exception as e:
            print(f"获取贴吧热帖失败: {e}")
        return []
