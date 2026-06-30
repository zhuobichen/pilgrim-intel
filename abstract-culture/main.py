"""抽象文化每日追踪器 - 主程序入口"""
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Any

from config import Config
from fetcher import (
    ZhihuFetcher, WeiboFetcher, BilibiliFetcher, TiebaFetcher, GitHubFetcher, DouyinFetcher,
    RedditFetcher, BaiduHotFetcher, ToutiaoFetcher, Kr36Fetcher, ThePaperFetcher,
    WallStreetCNFetcher, ITHomeFetcher, SSPaiFetcher, HackerNewsFetcher,
    TechCrunchFetcher, TheVergeFetcher, BBCNewsFetcher,
    ReutersFetcher, ProductHuntFetcher, DevToFetcher,
    GoogleNewsFetcher, ArsTechnicaFetcher,
)
from analyzer import LLMAnalyzer
from pusher import push_to_serverchan, push_to_bark, push_to_telegram, push_to_dingtalk, push_to_email


class HotTopicTracker:
    """热点追踪器主类"""

    def __init__(self):
        self.timeout = Config.CRAWLER_TIMEOUT
        self.max_concurrency = Config.CRAWLER_MAX_CONCURRENCY
        self.analyzer = LLMAnalyzer()

    async def fetch_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """并发抓取所有平台的热点数据"""
        print("=" * 60)
        print("开始抓取各平台热点数据...")
        print("=" * 60)

        # 创建所有抓取器实例
        fetchers = {
            # 核心社交平台
            '微博': WeiboFetcher(self.timeout),
            'B站热搜': BilibiliFetcher(self.timeout),
            '抖音': DouyinFetcher(self.timeout),
            '知乎': ZhihuFetcher(self.timeout),
            # 综合资讯
            '百度热搜': BaiduHotFetcher(self.timeout),
            '今日头条': ToutiaoFetcher(self.timeout),
            '澎湃新闻': ThePaperFetcher(self.timeout),
            # 科技财经
            '36氪': Kr36Fetcher(self.timeout),
            '华尔街见闻': WallStreetCNFetcher(self.timeout),
            'IT之家': ITHomeFetcher(self.timeout),
            '少数派': SSPaiFetcher(self.timeout),
            'HackerNews': HackerNewsFetcher(self.timeout),
            # 社区/论坛
            '贴吧': TiebaFetcher(self.timeout),
            'GitHub': GitHubFetcher(self.timeout),
            'Reddit': RedditFetcher(self.timeout),
            # 🌍 国外信源
            'TechCrunch': TechCrunchFetcher(self.timeout),
            'TheVerge': TheVergeFetcher(self.timeout),
            'BBC': BBCNewsFetcher(self.timeout),
            'Reuters': ReutersFetcher(self.timeout),
            'ProductHunt': ProductHuntFetcher(self.timeout),
            'DEV.to': DevToFetcher(self.timeout),
            'GoogleNews': GoogleNewsFetcher(self.timeout),
            'ArsTechnica': ArsTechnicaFetcher(self.timeout),
        }

        results = {}

        # 使用 semaphore 控制并发数
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def fetch_with_limit(name: str, fetcher):
            async with semaphore:
                # 添加随机延迟，避免同时请求
                await asyncio.sleep(random.uniform(0.5, 2))
                async with fetcher:
                    data = await fetcher.fetch()
                    print(f"✅ {name}: 获取到 {len(data)} 条热点")
                    return name, data

        # 并发执行所有抓取任务
        tasks = [
            fetch_with_limit(name, fetcher)
            for name, fetcher in fetchers.items()
        ]

        # 使用 return_exceptions=True 确保单个失败不影响其他
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                print(f"❌ 抓取失败: {result}")
                continue
            name, data = result
            results[name] = data

        total = sum(len(items) for items in results.values())
        print(f"\n📊 总计抓取到 {total} 条热点数据")
        return results

    async def generate_report(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        """生成分析报告"""
        print("\n" + "=" * 60)
        print("正在调用 AI 生成抽象文化日报...")
        print("=" * 60)

        report = await self.analyzer.analyze(data)
        return report

    def save_report(self, report: str) -> str:
        """保存报告到文件"""
        Config.ensure_dirs()
        today = datetime.now().strftime('%Y%m%d')
        filename = f"abstract_daily_{today}.md"
        filepath = f"{Config.REPORTS_DIR}/{filename}"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"\n📝 报告已保存: {filepath}")
        return filepath

    def push_report(self, title: str, content: str):
        """推送报告到配置的渠道"""
        if Config.PUSH_TYPE == 'none':
            print("\n📭 未配置推送，跳过")
            return

        print(f"\n📤 正在推送到 {Config.PUSH_TYPE}...")

        pushers = {
            'email': push_to_email,
            'serverchan': push_to_serverchan,
            'bark': push_to_bark,
            'telegram': push_to_telegram,
            'dingtalk': push_to_dingtalk,
        }

        pusher = pushers.get(Config.PUSH_TYPE)
        if pusher:
            pusher(title, content)
        else:
            print(f"不支持的推送类型: {Config.PUSH_TYPE}")

    async def run(self):
        """运行完整流程"""
        start_time = datetime.now()
        print("\n🚀 抽象文化每日追踪器启动")
        print(f"⏰ 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # 1. 抓取数据
            data = await self.fetch_all()

            # 2. 生成报告
            report = await self.generate_report(data)

            # 3. 输出到终端
            print("\n" + "=" * 60)
            print("📰 抽象文化日报")
            print("=" * 60)
            print(report)

            # 4. 保存报告
            self.save_report(report)

            # 5. 推送报告
            title = f"抽象文化日报 {datetime.now().strftime('%Y-%m-%d')}"
            self.push_report(title, report)

        except Exception as e:
            print(f"\n❌ 运行出错: {e}")
            import traceback
            traceback.print_exc()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\n🏁 完成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  总耗时: {duration:.1f} 秒")


async def main():
    """主函数"""
    tracker = HotTopicTracker()
    await tracker.run()


if __name__ == '__main__':
    asyncio.run(main())
