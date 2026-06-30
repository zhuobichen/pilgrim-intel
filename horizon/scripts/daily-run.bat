@echo off
REM Horizon Daily Runner
REM Sets UTF-8 encoding and runs Horizon

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\Horizon

echo [%date% %time%] Horizon daily run started >> E:\CodeProject\Horizon\data\cron.log
uv run horizon >> E:\CodeProject\Horizon\data\cron.log 2>&1
echo [%date% %time%] Horizon daily run completed >> E:\CodeProject\Horizon\data\cron.log
