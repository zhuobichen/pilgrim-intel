"""Telegram推送模块"""
import requests
from config import Config


def push_to_telegram(title: str, content: str) -> bool:
    """Telegram推送，适合海外用户"""
    try:
        token = Config.TELEGRAM_BOT_TOKEN
        chat_id = Config.TELEGRAM_CHAT_ID
        if not token or not chat_id:
            print("未配置 Telegram Bot Token 或 Chat ID，跳过推送")
            return False

        # 内容过长时截断
        if len(content) > 4000:
            content = content[:4000] + "..."

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": f"*{title}*\n\n{content}",
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        if response.status_code == 200:
            print("Telegram推送成功")
            return True
        else:
            print(f"Telegram推送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"Telegram推送异常: {e}")
        return False
