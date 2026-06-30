@echo off
REM GameHub Daily Digest Runner

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\GameHub\cli

REM Load .env
for /f "tokens=1,2 delims==" %%a in (.env) do set %%a=%%b

echo [%date% %time%] GameHub daily digest started >> %USERPROFILE%\.gamehub\cron.log
python daily_digest.py >> %USERPROFILE%\.gamehub\cron.log 2>&1
echo [%date% %time%] GameHub daily digest completed >> %USERPROFILE%\.gamehub\cron.log
