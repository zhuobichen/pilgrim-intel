"""配置管理模块"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """集中配置管理"""

    # AI 配置
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
    AI_MODEL = os.getenv('AI_MODEL', 'deepseek-chat')
    AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '4000'))
    AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0.8'))

    # 抓取配置
    CRAWLER_TIMEOUT = int(os.getenv('CRAWLER_TIMEOUT', '20'))
    CRAWLER_MAX_CONCURRENCY = int(os.getenv('CRAWLER_MAX_CONCURRENCY', '6'))

    # 推送配置
    PUSH_TYPE = os.getenv('PUSH_TYPE', 'none')

    # 邮件推送
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.qq.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '465'))
    EMAIL_USER = os.getenv('EMAIL_USER', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    EMAIL_TO = os.getenv('EMAIL_TO', '')

    # 其他推送
    SERVERCHAN_KEY = os.getenv('SERVERCHAN_KEY', '')
    BARK_KEY = os.getenv('BARK_KEY', '')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    DINGTALK_WEBHOOK = os.getenv('DINGTALK_WEBHOOK', '')
    DINGTALK_SECRET = os.getenv('DINGTALK_SECRET', '')

    # 路径配置
    REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')

    @classmethod
    def ensure_dirs(cls):
        """确保必要的目录存在"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
