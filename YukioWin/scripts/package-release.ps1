param([string]$Version = "", [string]$Output = "dist/releases")
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not $Version) { $Version = python -c "from yukio import __version__; print(__version__)" }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Expected stable semantic version' }
vpk pack --packId YukioDesktop --packVersion $Version --packDir dist/Yukio --mainExe Yukio.exe --packTitle Yukio --packAuthors leozhang8654 --icon Resources/Yukio.ico --releaseNotes ../docs/releases/0.4.0.md --outputDir $Output
if ($LASTEXITCODE -ne 0) { throw 'Velopack packaging failed' }
