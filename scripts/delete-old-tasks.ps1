Unregister-ScheduledTask -TaskName "AbstractCultureDaily" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "TrendRadarDailyReport" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "GameHubDailyDigest" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "HorizonDailyReport" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "All 4 old tasks deleted"
