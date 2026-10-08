$ErrorActionPreference = 'Stop'
$test = Join-Path $PWD 'build/update-test'
New-Item -ItemType Directory -Force $test | Out-Null
$install = Join-Path $test 'installed'
$setup = (Get-ChildItem build/update-baseline/*Setup.exe | Select-Object -First 1).FullName
$p = Start-Process $setup -ArgumentList @('--silent', '--installto', "`"$install`"") -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Baseline install failed: $($p.ExitCode)" }
$source = (Resolve-Path dist/releases).Path
$report = Join-Path $test 'upgrade-result.json'
$p = Start-Process (Join-Path $install 'current/Yukio.exe') -ArgumentList @('--update-smoke', "`"$source`"", "`"$report`"") -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Upgrade initiation failed: $($p.ExitCode)" }
$deadline = (Get-Date).AddMinutes(2)
while (-not (Test-Path $report) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
if (-not (Test-Path $report)) { throw 'Updated application did not restart and verify' }
Get-Content $report
# Launch the updated installed binary through the existing native UI smoke test.
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -Exe "$install/current/Yukio.exe" -OutDir "$test/native-smoke"
if ($LASTEXITCODE -ne 0) { throw 'Updated installation failed native smoke test' }
