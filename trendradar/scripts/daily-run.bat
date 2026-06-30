@echo off
REM TrendRadar Daily Runner — pilgrim-intel edition
REM 热点聚合 + RSS → HTML 报告 → 多推送

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\TrendRadar

echo [%date% %time%] TrendRadar started >> E:\CodeProject\pilgrim-intel\logs\trendradar.log
.venv\Scripts\python.exe -m trendradar >> E:\CodeProject\pilgrim-intel\logs\trendradar.log 2>&1
echo [%date% %time%] TrendRadar completed >> E:\CodeProject\pilgrim-intel\logs\trendradar.log
