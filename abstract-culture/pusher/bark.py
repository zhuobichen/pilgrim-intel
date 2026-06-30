"""Bark推送模块"""
import requests
from config import Config


def push_to_bark(title: str, content: str) -> bool:
    """Bark推送，适合iPhone用户"""
    try:
        key = Config.BARK_KEY
        if not key:
            print("未配置 Bark Key，跳过推送")
            return False

        # 内容过长时截断
        if len(content) > 1000:
            content = content[:1000] + "..."

        url = f"https://api.day.app/{key}/{title}/{content}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("Bark推送成功")
            return True
        else:
            print(f"Bark推送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"Bark推送异常: {e}")
        return False
