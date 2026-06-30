$taskName = "TrendRadarDailyReport"
$description = "TrendRadar hot news aggregation - 11 platforms + DeepSeek + email"

Unregister-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue -Confirm:$false

$trigger = New-ScheduledTaskTrigger -Daily -At 18:30
$action = New-ScheduledTaskAction -Execute "E:\CodeProject\TrendRadar\scripts\daily-run.bat"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Description $description -Force

Write-Host "OK: $taskName at 18:30"
Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State
