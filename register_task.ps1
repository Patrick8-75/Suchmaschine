<#
Registriert die Windows-Aufgabenplanung fuer die Maschinensuche.
Laeuft werktags wie kalenderlos taeglich um 7,9,11,13,15,17,19,21 Uhr (lokale Zeit).

Aufruf (einmalig, in einer normalen PowerShell, kein Admin noetig):
    powershell -ExecutionPolicy Bypass -File register_task.ps1
#>

$taskName = "Maschinensuche - P.Urny Handel"
$scriptPath = Join-Path $PSScriptRoot "scripts\maschinensuche_lokal.py"
$pythonExe = (Get-Command python).Source

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`"" -WorkingDirectory $PSScriptRoot

$zeiten = @(7,9,11,13,15,17,19,21)
$trigger = foreach ($stunde in $zeiten) {
    New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($stunde))
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Sucht mehrmals taeglich auf Gebrauchtmaschinen-Portalen nach neuen Anzeigen (Claas Conspeed, Geringhoff)." -Force

Write-Host "Aufgabe '$taskName' angelegt: taeglich um $($zeiten -join ', ') Uhr."
Write-Host "Test-Lauf jetzt sofort: Start-ScheduledTask -TaskName '$taskName'"
