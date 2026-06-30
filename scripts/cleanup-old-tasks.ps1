Unregister-ScheduledTask -TaskName "PilgrimAbstractCulture" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "PilgrimTrendRadar" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "PilgrimGameHub" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "PilgrimHorizon" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Old 4 individual tasks cleaned up"
Write-Host "Active: PilgrimIntelDaily"
Get-ScheduledTask -TaskName "PilgrimIntelDaily" | Format-Table TaskName, State, NextRunTime
