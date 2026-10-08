@echo off
REM Pilgrim Intel — Unified Daily Runner
REM All feeds: abstract-culture / trendradar / gamehub / horizon + shenlun(独立邮件)
REM Logs: ..\logs\

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM 用脚本自身位置定位项目根，避免换目录后路径失效
cd /d "%~dp0.."

echo [%date% %time%] Pilgrim Intel daily run started >> logs\all.log
python run.py >> logs\all.log 2>&1
echo [%date% %time%] Pilgrim Intel daily run completed >> logs\all.log
