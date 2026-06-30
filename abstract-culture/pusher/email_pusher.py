"""邮件推送模块"""
import smtplib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from config import Config


def push_to_email(title: str, content: str) -> bool:
    """推送报告到邮件"""

    def _md_to_html(md: str) -> str:
        body = md
        body = re.sub(r'^### (.+)$', r'<h3 style="color:#374151;margin:18px 0 8px">\1</h3>', body, flags=re.M)
        body = re.sub(r'^## (.+)$', r'<h2 style="color:#1f2937;margin:22px 0 10px;border-bottom:2px solid #e5e7eb;padding-bottom:6px">\1</h2>', body, flags=re.M)
        body = re.sub(r'^# (.+)$', r'<h1 style="color:#111827;margin:0 0 8px;font-size:20px">\1</h1>', body, flags=re.M)
        body = re.sub(r'\*\*(.+?)\*\*', r'<b style="color:#1f2937">\1</b>', body)
        body = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#4f46e5;text-decoration:none">\1</a>', body)
        body = body.replace('\n\n', '<br><br>').replace('\n', '<br>')
        return body

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = title
        msg["From"] = Config.EMAIL_USER
        msg["To"] = Config.EMAIL_TO

        html_body = _md_to_html(content)
        full_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:#f3f4f6;color:#1f2937;padding:0;margin:0">
<div style="max-width:680px;margin:0 auto;padding:24px 16px">

<div style="background:linear-gradient(135deg,#18181b,#3f3f46);border-radius:14px;padding:28px 24px;margin-bottom:20px;text-align:center;box-shadow:0 4px 12px rgba(0,0,0,0.1)">
  <div style="font-size:28px;margin-bottom:4px">🌀</div>
  <h1 style="margin:0;font-size:22px;font-weight:700;color:#fafafa">抽象文化日报</h1>
  <p style="color:rgba(255,255,255,0.65);margin:8px 0 0;font-size:13px">{datetime.now().strftime('%Y-%m-%d %H:%M')} · 多平台热点追踪</p>
</div>

<div style="background:#fff;border-radius:12px;padding:24px 28px;box-shadow:0 1px 3px rgba(0,0,0,0.06);border:1px solid #e5e7eb;line-height:1.8">
{html_body}
</div>

<div style="text-align:center;margin-top:20px;color:#9ca3af;font-size:12px;line-height:1.6">
  Abstract Culture Tracker · 每日自动生成
</div>
</div></body></html>"""

        msg.attach(MIMEText(full_html, "html", "utf-8"))
        with smtplib.SMTP_SSL(Config.EMAIL_HOST, Config.EMAIL_PORT, timeout=15) as s:
            s.login(Config.EMAIL_USER, Config.EMAIL_PASSWORD)
            s.sendmail(Config.EMAIL_USER, [Config.EMAIL_TO], msg.as_string())
        print(f"✅ 邮件已发送至 {Config.EMAIL_TO}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False
