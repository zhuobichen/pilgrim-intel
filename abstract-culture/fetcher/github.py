"""GitHub Trending抓取器"""
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base import BaseFetcher


class GitHubFetcher(BaseFetcher):
    """GitHub Trending抓取器"""

    async def fetch(self) -> List[Dict[str, Any]]:
        """获取GitHub Trending"""
        try:
            url = 'https://github.com/trending'
            headers = self._get_headers()
            headers['Accept'] = 'text/html'

            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    items = []

                    # 解析 trending 仓库
                    articles = soup.find_all('article', class_='Box-row')
                    for article in articles[:15]:
                        a_tag = article.find('h2', class_='h3').find('a') if article.find('h2', class_='h3') else None
                        if a_tag:
                            title = a_tag.get_text(strip=True).replace('\n', '').replace(' ', '')
                            href = f"https://github.com{a_tag.get('href', '')}"

                            # 获取描述
                            desc_tag = article.find('p', class_='col-9')
                            desc = desc_tag.get_text(strip=True) if desc_tag else ''

                            # 获取star数
                            stars_tag = article.find('a', class_='Link--muted')
                            stars = stars_tag.get_text(strip=True) if stars_tag else ''

                            items.append({
                                'title': title,
                                'url': href,
                                'heat': stars,
                                'source': 'GitHub',
                                'description': desc
                            })

                    return self._clean_items(items)
        except Exception as e:
            print(f"获取GitHub Trending失败: {e}")
        return []
