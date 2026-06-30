"""数据抓取模块"""
from .base import BaseFetcher
from .zhihu import ZhihuFetcher
from .weibo import WeiboFetcher
from .bilibili import BilibiliFetcher
from .tieba import TiebaFetcher
from .github import GitHubFetcher
from .douyin import DouyinFetcher
from .reddit import RedditFetcher
from .baidu import BaiduHotFetcher
from .news_sites import (
    ToutiaoFetcher, Kr36Fetcher, ThePaperFetcher,
    WallStreetCNFetcher, ITHomeFetcher, SSPaiFetcher, HackerNewsFetcher,
    # 国外信源
    TechCrunchFetcher, TheVergeFetcher, BBCNewsFetcher,
    ReutersFetcher, ProductHuntFetcher, DevToFetcher,
    GoogleNewsFetcher, ArsTechnicaFetcher,
)

__all__ = [
    'BaseFetcher', 'ZhihuFetcher', 'WeiboFetcher', 'BilibiliFetcher',
    'TiebaFetcher', 'GitHubFetcher', 'DouyinFetcher', 'RedditFetcher',
    'BaiduHotFetcher', 'ToutiaoFetcher', 'Kr36Fetcher', 'ThePaperFetcher',
    'WallStreetCNFetcher', 'ITHomeFetcher', 'SSPaiFetcher', 'HackerNewsFetcher',
    'TechCrunchFetcher', 'TheVergeFetcher', 'BBCNewsFetcher',
    'ReutersFetcher', 'ProductHuntFetcher', 'DevToFetcher',
    'GoogleNewsFetcher', 'ArsTechnicaFetcher',
]
