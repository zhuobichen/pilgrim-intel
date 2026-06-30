@echo off
REM Abstract Culture Tracker Daily Runner — pilgrim-intel edition
REM 15 平台 → LLM 文化分析 → 邮件推送

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\pilgrim-intel\abstract-culture

echo [%date% %time%] Abstract Culture started >> E:\CodeProject\pilgrim-intel\logs\abstract-culture.log
python main.py >> E:\CodeProject\pilgrim-intel\logs\abstract-culture.log 2>&1
echo [%date% %time%] Abstract Culture completed >> E:\CodeProject\pilgrim-intel\logs\abstract-culture.log
