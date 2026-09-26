param([string]$Exe = "dist\Yukio.exe")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$out = Join-Path $PWD "build/assistant-smoke"
New-Item -ItemType Directory -Force $out | Out-Null
$env:LOCALAPPDATA = Join-Path $out "profile"
$env:YUKIO_REMINDER_FILE = Join-Path $out "reminders.json"
$report = Join-Path $out "report.json"
if (Test-Path $report) { Remove-Item $report }
$process = Start-Process -FilePath (Resolve-Path $Exe) -ArgumentList "--allow-multiple", "--assistant-only", "--assistant-smoke", "build/assistant-smoke" -PassThru
try {
    if (-not $process.WaitForExit(65000)) { throw "Assistant did not finish within 65 seconds" }
    if (-not (Test-Path $report)) { throw "Missing assistant smoke report" }
    $result = Get-Content $report -Raw | ConvertFrom-Json
    Get-Content $report
    if (-not $result.ok) { throw "Assistant smoke failed" }
    foreach ($name in @("home", "reminders", "extensions", "delivery")) {
        if (-not (Test-Path (Join-Path $out "$name.png"))) { throw "Missing $name screenshot" }
    }
} finally {
    Get-Process -Name Yukio -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
