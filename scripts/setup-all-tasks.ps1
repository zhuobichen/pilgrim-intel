$tasks = @(
    @{
        Name = "PilgrimAbstractCulture"
        Desc = "Pilgrim Intel — Abstract Culture Daily Tracker (15 sources + LLM + email)"
        Bat  = "E:\CodeProject\pilgrim-intel\abstract-culture\scripts\daily-run.bat"
    },
    @{
        Name = "PilgrimTrendRadar"
        Desc = "Pilgrim Intel — TrendRadar Hot News Aggregation (hotlist + RSS + HTML report)"
        Bat  = "E:\CodeProject\pilgrim-intel\trendradar\scripts\daily-run.bat"
    },
    @{
        Name = "PilgrimGameHub"
        Desc = "Pilgrim Intel — GameHub Game Daily Digest (15 game sources + DeepSeek)"
        Bat  = "E:\CodeProject\pilgrim-intel\gamehub\scripts\daily-run.bat"
    },
    @{
        Name = "PilgrimHorizon"
        Desc = "Pilgrim Intel — Horizon AI News Radar (CN+EN bilingual daily)"
        Bat  = "E:\CodeProject\pilgrim-intel\horizon\scripts\daily-run.bat"
    }
)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit 0 `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

foreach ($t in $tasks) {
    Unregister-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue -Confirm:$false

    # stagger by 2 min each: 18:30, 18:32, 18:34, 18:36
    # this prevents all 4 from hammering API/network at the same moment
    $triggers = @()

    # abstract: 18:30 | trendradar: 18:30 | gamehub: 18:34 | horizon: 18:36
    if ($t.Name -eq "PilgrimGameHub") {
        $trigger = New-ScheduledTaskTrigger -Daily -At 18:34
    } elseif ($t.Name -eq "PilgrimHorizon") {
        $trigger = New-ScheduledTaskTrigger -Daily -At 18:36
    } elseif ($t.Name -eq "PilgrimTrendRadar") {
        $trigger = New-ScheduledTaskTrigger -Daily -At 18:32
    } else {
        $trigger = New-ScheduledTaskTrigger -Daily -At 18:30
    }

    $action = New-ScheduledTaskAction -Execute $t.Bat
    Register-ScheduledTask -TaskName $t.Name -Trigger $trigger -Action $action -Settings $settings -Principal $principal -Description $t.Desc -Force
    Write-Host "OK: $($t.Name) at $($trigger.StartBoundary)"
}

Write-Host ""
Write-Host "=== All Pilgrim Intel tasks registered ==="
Get-ScheduledTask -TaskName "Pilgrim*" | Format-Table TaskName, State
