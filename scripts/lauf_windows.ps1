# Startet die Maschinensuche unabhaengig von der Claude-App.
# Wird von der Windows-Aufgabe "Maschinensuche P.Urny Handel" aufgerufen.
$ErrorActionPreference = 'Continue'
$repo   = 'C:\Users\Patrick.Urny\Maschinensuche-P.Urny-Handel'
$python = 'C:\Users\Patrick.Urny\AppData\Local\Programs\Python\Python312\python.exe'
$log    = Join-Path $repo 'logs\windows-task.log'

function Schreibe($text) {
    $zeile = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $text
    Add-Content -LiteralPath $log -Value $zeile -Encoding utf8
}

Set-Location -LiteralPath $repo
Schreibe "=== Windows-Aufgabe gestartet ==="

foreach ($skript in @('scripts\maschinensuche_lokal.py', 'scripts\render_radar.py')) {
    $ausgabe = & $python $skript 2>&1
    $code = $LASTEXITCODE
    Schreibe "$skript beendet mit Exitcode $code"
    foreach ($z in $ausgabe) { Schreibe "    $z" }
    # Bei Fehler im Suchlauf trotzdem weiter zum Rendern, damit das
    # 24h-Fenster im Radar korrekt ablaeuft.
}

Schreibe "=== Windows-Aufgabe beendet ==="
