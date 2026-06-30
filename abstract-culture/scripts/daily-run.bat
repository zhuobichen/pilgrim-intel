@echo off
REM Abstract Culture Tracker Daily Runner

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d E:\CodeProject\abstract_culture_tracker

echo [%date% %time%] Abstract Tracker started >> reports\cron.log
python main.py >> reports\cron.log 2>&1
echo [%date% %time%] Abstract Tracker completed >> reports\cron.log
