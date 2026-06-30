@echo off
REM Horizon Daily Runner — pilgrim-intel edition
REM AI 新闻雷达 → 中英双语日报

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\Horizon

echo [%date% %time%] Horizon started >> E:\CodeProject\pilgrim-intel\logs\horizon.log
uv run horizon >> E:\CodeProject\pilgrim-intel\logs\horizon.log 2>&1
echo [%date% %time%] Horizon completed >> E:\CodeProject\pilgrim-intel\logs\horizon.log
