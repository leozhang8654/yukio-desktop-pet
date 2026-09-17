# 在真 Windows 上实跑一遍打好的 Yukio.exe，确认她真的出来了、而且跟对了动作。
#
#   powershell -ExecutionPolicy Bypass -File scripts\smoke-test.ps1 -Exe dist\Yukio.exe
#
# 步骤：造一份 Deep Code 会话（一次 edit 调用）→ 启动 exe → 找她的窗口、量尺寸和样式
#      → 看她显示的动作对不对（YUKIO_STATE_FILE）→ 截屏 → 收工。
# 窗口没出来、动作不对、程序自己退了、或者写了 error.log，都算失败（退出码非 0）。
# 产物在 smoke\：window.txt、state.txt、screenshot.png、error.log（如果有）。

param(
    [string]$Exe = "dist\Yukio.exe",
    [string]$OutDir = "smoke",
    [int]$WaitSeconds = 10
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$out = Join-Path $root $OutDir
New-Item -ItemType Directory -Force -Path $out | Out-Null
if (-not (Test-Path $Exe)) { throw "没找到 $Exe" }

# 干净的第一次运行：清掉上次的设置和日志
$appData = Join-Path $env:LOCALAPPDATA "Yukio"
if (Test-Path $appData) { Remove-Item -Recurse -Force $appData }

Write-Host "== 造一份 Deep Code 会话"
python scripts\seed_smoke_session.py
if ($LASTEXITCODE -ne 0) { throw "造会话失败" }

$stateFile = Join-Path $out "state.txt"
if (Test-Path $stateFile) { Remove-Item $stateFile }
$env:YUKIO_STATE_FILE = $stateFile

Write-Host "== 启动 $Exe"
$process = Start-Process -FilePath (Resolve-Path $Exe) -ArgumentList "--allow-multiple" -PassThru
Start-Sleep -Seconds $WaitSeconds

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class YukioProbe {
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindowW(string cls, string name);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
    public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int index);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int left, top, right, bottom; }
}
"@

$report = New-Object System.Collections.Generic.List[string]
$failures = New-Object System.Collections.Generic.List[string]

if ($process.HasExited) { $failures.Add("程序启动后就退出了，退出码 $($process.ExitCode)") }

foreach ($cls in @("YukioPet", "YukioBubble", "YukioControl")) {
    $hwnd = [YukioProbe]::FindWindowW($cls, $null)
    if ($hwnd -eq [IntPtr]::Zero) {
        $report.Add("$cls : 没找到")
        if ($cls -ne "YukioBubble") { $failures.Add("找不到窗口 $cls") }
        continue
    }
    $rect = New-Object YukioProbe+RECT
    [void][YukioProbe]::GetWindowRect($hwnd, [ref]$rect)
    $visible = [YukioProbe]::IsWindowVisible($hwnd)
    $w = $rect.right - $rect.left
    $h = $rect.bottom - $rect.top
    $exStyle = [int64][YukioProbe]::GetWindowLongPtr($hwnd, -20)
    $report.Add(("{0} : hwnd={1} 可见={2} 位置=({3},{4}) 大小={5}x{6} exStyle=0x{7:X}" -f `
        $cls, $hwnd, $visible, $rect.left, $rect.top, $w, $h, $exStyle))
    if ($cls -eq "YukioPet") {
        if (-not $visible) { $failures.Add("雪绪的窗口没有显示出来") }
        if ($w -lt 150 -or $h -lt 150) { $failures.Add("雪绪的窗口尺寸不对：${w}x${h}（应该 192x208 左右）") }
        if (($exStyle -band 0x80000) -eq 0) { $failures.Add("雪绪的窗口没有 WS_EX_LAYERED，逐像素透明不生效") }
    }
}

# 她当前显示的动作：应该是“纸上书写”，气泡写“编辑 login.py”
if (Test-Path $stateFile) {
    $state = Get-Content $stateFile -Encoding UTF8
    $report.Add("state.txt：" + ($state -join " | "))
    if ($state[0] -ne "write_file") {
        $failures.Add("动作不对：期望 write_file，实际 $($state[0])（会话记录没读进去？）")
    }
} else {
    $failures.Add("没写出 state.txt：主循环可能没跑起来")
}

# 截屏（没有桌面的环境下会失败，不算错）
try {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save((Join-Path $out "screenshot.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $report.Add("截屏：$($bounds.Width)x$($bounds.Height)")
} catch {
    $report.Add("截屏失败（这个环境可能没有桌面）：$($_.Exception.Message)")
}

$log = Join-Path $appData "error.log"
if (Test-Path $log) {
    Copy-Item $log (Join-Path $out "error.log")
    $text = Get-Content $log -Raw
    $report.Add("error.log：`n$text")
    if ($text -match "Traceback") { $failures.Add("运行时写了 error.log，里面有 Traceback") }
}
$settings = Join-Path $appData "settings.json"
if (Test-Path $settings) { $report.Add("settings.json：$((Get-Content $settings -Raw) -replace "`r`n", " ")") }
else { $failures.Add("没写出 settings.json（设置没保存？）") }

if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }

$report.Add("失败项：" + $(if ($failures.Count) { $failures -join "；" } else { "无" }))
$text = $report -join "`r`n"
Set-Content -Path (Join-Path $out "window.txt") -Value $text -Encoding UTF8
Write-Host $text

if ($failures.Count) { exit 1 }
Write-Host "== 冒烟测试通过：窗口在、可见、分层、尺寸对、动作跟对了"
exit 0
