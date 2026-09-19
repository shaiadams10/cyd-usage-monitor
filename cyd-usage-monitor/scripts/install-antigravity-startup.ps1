param([Parameter(Mandatory)][string]$Pythonw, [Parameter(Mandatory)][string]$Watcher)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Pythonw -PathType Leaf) -or
    -not (Test-Path -LiteralPath $Watcher -PathType Leaf)) { throw 'Installed watcher is missing.' }
$taskName = 'CYD Antigravity Messages'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $Pythonw -Argument ('"' + $Watcher + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$trigger.Delay = 'PT10S'
# A separate timer is active immediately, even before the first logon trigger.
# IgnoreNew prevents launches while the watcher is running; no polling process.
$recovery = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$old = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$legacyWatcher = Join-Path $env:LOCALAPPDATA 'CYDUsageMonitor\watch-antigravity-messages.py'
if ($old) {
    if ([IO.Path]::GetFileName($old.Actions.Execute) -ne 'pythonw.exe' -or $old.Actions.Arguments -notin @(('"' + $Watcher + '"'), ('"' + $legacyWatcher + '"'))) {
        throw 'A different task owns the CYD startup name.'
    }
    Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path (Split-Path $Watcher) 'startup-task-backup.xml')
}
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($trigger, $recovery) -Principal $principal -Settings $settings -Force | Out-Null
# Retire only the exact installed watcher, including a legacy Run-launched copy.
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" | Where-Object {
    $_.ExecutablePath -in @($Pythonw, $old.Actions.Execute) -and (
        $_.CommandLine -match ('(?:^|[\s"])' + [regex]::Escape($Watcher) + '(?:["\s]|$)') -or
        $_.CommandLine -match ('(?:^|[\s"])' + [regex]::Escape($legacyWatcher) + '(?:["\s]|$)'))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
# Migrate only our legacy startup value after registration succeeds.
Remove-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name CYDAntigravityMessages -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 1
if ((Get-ScheduledTask -TaskName $taskName).State -ne 'Running') {
    throw 'Task was registered but did not stay running; inspect status and task result.'
}
Write-Output 'Registered and started the per-user CYD task with logon and failure recovery.'
