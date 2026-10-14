param([string]$Version = "", [string]$Output = "dist/releases")
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not $Version) { $Version = python -c "from yukio import __version__; print(__version__)" }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Expected stable semantic version' }
$Notes = "../docs/releases/$Version.md"
if ($Version -eq '0.3.99') {
    # The internal upgrade baseline has no public release notes.
    New-Item -ItemType Directory -Force build | Out-Null
    $Notes = 'build/upgrade-baseline-notes.md'
    'Internal upgrade test baseline.' | Set-Content -Encoding UTF8 $Notes
} elseif (-not (Test-Path $Notes)) {
    throw "Missing release notes for $Version"
}
vpk pack --runtime win-x64 --packId YukioDesktop --packVersion $Version --packDir dist/Yukio --mainExe Yukio.exe --packTitle Yukio --packAuthors leozhang8654 --icon Resources/Yukio.ico --releaseNotes $Notes --outputDir $Output
if ($LASTEXITCODE -ne 0) { throw 'Velopack packaging failed' }
