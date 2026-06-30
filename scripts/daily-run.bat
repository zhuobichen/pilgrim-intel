@echo off
REM Pilgrim Intel — Unified Daily Runner
REM All 4 feeds: abstract-culture → trendradar → gamehub → horizon
REM Logs: ..\logs\

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\pilgrim-intel

echo [%date% %time%] Pilgrim Intel daily run started >> logs\all.log
python run.py >> logs\all.log 2>&1
echo [%date% %time%] Pilgrim Intel daily run completed >> logs\all.log
