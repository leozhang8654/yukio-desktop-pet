$ErrorActionPreference = 'Stop'
$test = Join-Path $PWD 'build/update-test'
New-Item -ItemType Directory -Force $test | Out-Null
function Run-Bounded($Exe, $Arguments, $Label) {
    Write-Host "== $Label : $Exe $Arguments"
    $p = Start-Process $Exe -ArgumentList $Arguments -PassThru
    if (-not $p.WaitForExit(60000)) {
        python -c "from PIL import ImageGrab; ImageGrab.grab().save(r'$test/timeout.png')"
        Get-Process | Where-Object { $_.MainWindowTitle } | Select-Object Name,Id,MainWindowTitle | Out-File "$test/windows.txt"
        Get-Content "$test/windows.txt"
        Stop-Process -Id $p.Id -Force
        throw "$Label timed out"
    }
    if ($p.ExitCode -ne 0) { throw "$Label failed: $($p.ExitCode)" }
}
$install = Join-Path $test 'installed'
$setup = (Get-ChildItem build/update-baseline/*Setup.exe | Select-Object -First 1).FullName
Run-Bounded $setup @('--silent', '--installto', "`"$install`"") 'Baseline installation'
$source = (Resolve-Path dist/releases).Path
$report = Join-Path $test 'upgrade-result.json'
Run-Bounded (Join-Path $install 'current/Yukio.exe') @('--update-smoke', "`"$source`"", "`"$report`"") 'Upgrade initiation'
$deadline = (Get-Date).AddMinutes(1)
while (-not (Test-Path $report) -and (Get-Date) -lt $deadline) {
    if (Test-Path "$test/upgrade-result.error.txt") { Get-Content "$test/upgrade-result.error.txt"; throw 'Upgrade failed' }
    Start-Sleep -Seconds 1
}
if (-not (Test-Path $report)) { throw 'Updated application did not restart and verify' }
Get-Content $report
# Launch the updated installed binary through the existing native UI smoke test.
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1 -Exe "$install/current/Yukio.exe" -OutDir "build/update-test/native-smoke"
if ($LASTEXITCODE -ne 0) { throw 'Updated installation failed native smoke test' }
