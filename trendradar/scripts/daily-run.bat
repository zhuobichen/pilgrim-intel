@echo off
REM TrendRadar Daily Runner
REM Sets UTF-8 encoding and runs TrendRadar

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\TrendRadar

echo [%date% %time%] TrendRadar daily run started >> E:\CodeProject\TrendRadar\output\cron.log
.venv\Scripts\python.exe -m trendradar >> E:\CodeProject\TrendRadar\output\cron.log 2>&1
echo [%date% %time%] TrendRadar daily run completed >> E:\CodeProject\TrendRadar\output\cron.log
