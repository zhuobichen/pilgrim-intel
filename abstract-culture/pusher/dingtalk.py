"""钉钉推送模块"""
import hashlib
import hmac
import time
import base64
import requests
from config import Config


def push_to_dingtalk(title: str, content: str) -> bool:
    """钉钉群机器人推送，适合团队使用"""
    try:
        webhook = Config.DINGTALK_WEBHOOK
        secret = Config.DINGTALK_SECRET
        if not webhook:
            print("未配置钉钉 Webhook，跳过推送")
            return False

        timestamp = str(round(time.time() * 1000))

        # 如果有 secret，计算签名
        if secret:
            sign_string = f"{timestamp}\n{secret}"
            sign = base64.b64encode(
                hmac.new(secret.encode(), sign_string.encode(), hashlib.sha256).digest()
            ).decode()
            params = {"timestamp": timestamp, "sign": sign}
        else:
            params = {}

        response = requests.post(
            webhook,
            json={
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"## {title}\n\n{content}"
                }
            },
            params=params,
            timeout=10
        )
        if response.status_code == 200:
            print("钉钉推送成功")
            return True
        else:
            print(f"钉钉推送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"钉钉推送异常: {e}")
        return False
