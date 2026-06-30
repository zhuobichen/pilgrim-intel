@echo off
REM GameHub Daily Digest Runner — pilgrim-intel edition
REM 15 游戏信源 → DeepSeek 精选 → 邮件推送

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\pilgrim-intel\gamehub

echo [%date% %time%] GameHub started >> E:\CodeProject\pilgrim-intel\logs\gamehub.log
python daily_digest.py >> E:\CodeProject\pilgrim-intel\logs\gamehub.log 2>&1
echo [%date% %time%] GameHub completed >> E:\CodeProject\pilgrim-intel\logs\gamehub.log
