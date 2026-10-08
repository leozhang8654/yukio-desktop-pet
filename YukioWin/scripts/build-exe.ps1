# 在 Windows 上把雪绪打成一个 Yukio.exe。
#
#   cd YukioWin
#   powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1
#
# 需要：Python 3.9 或更新（勾选“Add python.exe to PATH”安装即可）。
# 产物：dist\Yukio\Yukio.exe，是程序目录；分发 dist\releases 下的 Setup 安装包。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = "python"
try { & $python --version | Out-Null } catch { $python = "py" }
& $python --version

$venv = Join-Path $root "build\venv"
if (-not (Test-Path $venv)) {
    Write-Host "== 建虚拟环境 build\venv"
    & $python -m venv $venv
}
$venvPython = Join-Path $venv "Scripts\python.exe"

Write-Host "== 装依赖（requirements.txt、pyinstaller）"
& $venvPython -m pip install --upgrade pip | Out-Null
& $venvPython -m pip install --upgrade pyinstaller -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

Write-Host "== 先跑一遍自测"
& $venvPython run.py --selftest
if ($LASTEXITCODE -ne 0) { throw "自测没过，先别打包" }

Write-Host "== 生成 Windows 低内存分页素材"
& $venvPython scripts\prepare-windows-assets.py
if ($LASTEXITCODE -ne 0) { throw "Windows 素材分页失败" }

Write-Host "== 打包"
& $venvPython -m PyInstaller --noconfirm --clean scripts\yukio.spec
if ($LASTEXITCODE -ne 0) { throw "打包失败" }

$exe = Join-Path $root "dist\Yukio\Yukio.exe"
if (-not (Test-Path $exe)) { throw "没找到 dist\Yukio\Yukio.exe" }
$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ""
Write-Host "好了：$exe（$size MB）"
Write-Host "双击就能跑；托盘里会多一个雪绪的小头像，右键她本人也能出菜单。"

& powershell -ExecutionPolicy Bypass -File scripts\package-release.ps1
if ($LASTEXITCODE -ne 0) { throw "安装包生成失败" }
