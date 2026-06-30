"""大模型分析模块"""
import os
from typing import List, Dict, Any
from datetime import datetime
from openai import AsyncOpenAI
from config import Config


class LLMAnalyzer:
    """基于大模型的热点分析器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
        )
        self.model = Config.AI_MODEL
        self.max_tokens = Config.AI_MAX_TOKENS
        self.temperature = Config.AI_TEMPERATURE

    def _build_prompt(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        today = datetime.now().strftime('%Y年%m月%d日')

        content_parts = []
        for source, items in data.items():
            if items:
                content_parts.append(f"\n【{source}】（{len(items)}条）")
                for i, item in enumerate(items[:10], 1):
                    heat = item.get('heat', '')
                    heat_str = f" [热度: {heat}]" if heat else ""
                    content_parts.append(f"{i}. {item['title']}{heat_str}")

        hot_topics = '\n'.join(content_parts)

        prompt = f"""你是精通中文互联网抽象文化的资深冲浪选手。注意：你生成的日报必须覆盖多个领域，不能只盯着体育。

今天是 {today}，以下是从 {len(data)} 个平台抓取的海量热点数据（覆盖社会、科技、财经、娱乐、游戏、互联网文化等领域）：

{hot_topics}

请生成一份**覆盖面广、视角多元**的"抽象文化日报"。严格要求：

## ⚠️ 领域均衡要求
- 如果原始数据中体育类内容过多，**最多选1条最有梗的体育新闻**
- 必须覆盖至少 4 个不同领域：社会热点、科技/数码、互联网文化/梗、财经/商业、娱乐/游戏
- 从不同平台各取精华，不要只盯着一个平台

## 1. 今日十大抽象热点（10-12条）
从各平台筛选最有趣的内容，**领域必须多样化**。每条配一句"抽象点评"（幽默毒舌，不超过35字）。格式：
1. **[标签：科技/社会/财经等]** 标题 —— 抽象点评

## 2. 新梗/热词解析
解释当天出现的网络新梗或热词，没有就写"今日暂无新梗诞生"，不硬凑。

## 3. 各平台氛围速览
用一句话概括每个平台今天的调性（要有梗）。

## 4. 抽象文化深度观察
从今日热点中提炼1个值得深度探讨的现象，分析背后的年轻人心态和社会情绪。不要太长，300字内。

要求：
- 语气轻松毒舌，略有嘲讽但不恶意
- 多用网络流行语和梗，但不要过度
- 体育内容严格控制占比（最多1条！）
- 优先关注：互联网文化、科技数码、社会现象、财经趣闻、游戏娱乐
"""
        return prompt

    async def analyze(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        if not Config.OPENAI_API_KEY:
            return "⚠️ 未配置AI API密钥"

        try:
            prompt = self._build_prompt(data)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是精通中文互联网抽象文化的冲浪高手。你的日报必须领域多元、见解毒辣、语言幽默。体育内容严格控制在1条以内。优先关注互联网文化、科技、社会、娱乐方向。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ AI分析失败: {str(e)}"
