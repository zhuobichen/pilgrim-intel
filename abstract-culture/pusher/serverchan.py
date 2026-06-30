"""Server酱推送模块"""
import os
import requests
from config import Config


def push_to_serverchan(title: str, content: str) -> bool:
    """Server酱推送，适合微信接收"""
    try:
        key = Config.SERVERCHAN_KEY
        if not key:
            print("未配置 Server酱 Key，跳过推送")
            return False

        url = f"https://sctapi.ftqq.com/{key}.send"
        response = requests.post(
            url,
            data={"title": title, "desp": content},
            timeout=10
        )
        if response.status_code == 200:
            print("Server酱推送成功")
            return True
        else:
            print(f"Server酱推送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"Server酱推送异常: {e}")
        return False
