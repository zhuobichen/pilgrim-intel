$taskName = "PilgrimIntelDaily"
$description = "Pilgrim Intel — AI News Aggregation (abstract-culture + trendradar + gamehub + horizon; shenlun 独立邮件)"

Unregister-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue -Confirm:$false

$batPath = Join-Path $PSScriptRoot "daily-run.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 18:30
$action = New-ScheduledTaskAction -Execute $batPath
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit 0 `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Description $description -Force

Write-Host "OK: PilgrimIntelDaily at 18:30"
Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State, NextRunTime
