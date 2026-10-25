$ErrorActionPreference = 'Stop'
$runnerRoot = Split-Path -Parent $PSScriptRoot
$runnerPython = 'C:\Users\User\Documents\Codex\2026-10-04\dlrj\work\nt8-mcp\.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $runnerPython)) { throw 'Python runtime missing' }
$runnerUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$runnerAction = New-ScheduledTaskAction -Execute $runnerPython -Argument '-m runner.service' -WorkingDirectory $runnerRoot
$runnerTrigger = New-ScheduledTaskTrigger -AtLogOn -User $runnerUser
$runnerPrincipal = New-ScheduledTaskPrincipal -UserId $runnerUser -LogonType Interactive -RunLevel Limited
$runnerSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'QVSD-NQ-Experiment-Runner' -Action $runnerAction -Trigger $runnerTrigger -Principal $runnerPrincipal -Settings $runnerSettings -Description 'Finite NQ research queue only; no live trading' -Force | Select-Object TaskName, State
Start-ScheduledTask -TaskName 'QVSD-NQ-Experiment-Runner'
