param([string]$Python = "python", [string]$Out = "build\interaction-check")
$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & $Python -m yukio --check
    if ($LASTEXITCODE -ne 0) { throw "Resource check failed" }
    & $Python -m yukio --interaction-check $Out
    if ($LASTEXITCODE -ne 0) { throw "Native interaction check failed" }
    Write-Host "Native report: $Out\windows-native.json. Complete the manual input/DPI/occlusion checklist separately."
} finally { Pop-Location }
