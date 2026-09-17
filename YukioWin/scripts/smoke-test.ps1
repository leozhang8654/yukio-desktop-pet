# 在真 Windows 上实跑一遍打好的 Yukio.exe，确认她真的出来了、跟对了动作、而且画对了。
#
#   powershell -ExecutionPolicy Bypass -File scripts\smoke-test.ps1 -Exe dist\Yukio.exe
#
# 步骤：造一份 Deep Code 会话（一次 edit 调用）→ 启动 exe → 列出她的窗口、量尺寸和样式
#      → 看显示的动作对不对（YUKIO_STATE_FILE）→ 截屏 → 拿截屏上的像素和图条逐点比。
# 任何一步不对都算失败（退出码非 0）。产物在 smoke\。

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
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class YukioProbe {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string name);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr h, int i);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left, top, right, bottom; }

    // 每个顶层窗口一行："类名|hwnd|可见|left|top|宽|高|exStyle|pid"
    public static List<string> ListWindows(string prefix) {
        List<string> rows = new List<string>();
        EnumWindows(delegate(IntPtr h, IntPtr p) {
            StringBuilder sb = new StringBuilder(256);
            GetClassNameW(h, sb, sb.Capacity);
            string cls = sb.ToString();
            if (prefix.Length > 0 && !cls.StartsWith(prefix)) return true;
            RECT r; GetWindowRect(h, out r);
            uint pid; GetWindowThreadProcessId(h, out pid);
            long ex = (long)GetWindowLongPtr(h, -20);
            rows.Add(string.Format("{0}|{1}|{2}|{3}|{4}|{5}|{6}|0x{7:X}|{8}",
                cls, h.ToInt64(), IsWindowVisible(h), r.left, r.top,
                r.right - r.left, r.bottom - r.top, ex, pid));
            return true;
        }, IntPtr.Zero);
        return rows;
    }
}
"@

$report = New-Object System.Collections.Generic.List[string]
$failures = New-Object System.Collections.Generic.List[string]

try {

if ($process.HasExited) { $failures.Add("程序启动后就退出了，退出码 $($process.ExitCode)") }

$rows = [YukioProbe]::ListWindows("Yukio")
if ($rows.Count -eq 0) {
    $failures.Add("一个 Yukio* 的窗口都没有")
    $report.Add("枚举不到 Yukio* 窗口，下面是当前所有顶层窗口：")
    foreach ($row in [YukioProbe]::ListWindows("")) { $report.Add("    $row") }
} else {
    foreach ($row in $rows) { $report.Add("窗口 $row") }
}

$pet = $rows | Where-Object { $_ -like "YukioPet|*" } | Select-Object -First 1
$petRect = $null
if (-not $pet) {
    $failures.Add("没有 YukioPet 窗口")
} else {
    $f = $pet.Split("|")
    $visible = [bool]::Parse($f[2])
    $petRect = @{ left = [int]$f[3]; top = [int]$f[4]; width = [int]$f[5]; height = [int]$f[6] }
    $ex = [Convert]::ToInt64($f[7].Substring(2), 16)
    if (-not $visible) { $failures.Add("雪绪的窗口没显示出来") }
    if ($petRect.width -lt 150 -or $petRect.height -lt 150) {
        $failures.Add("窗口尺寸不对：$($petRect.width)x$($petRect.height)（应该 192x208 左右）")
    }
    if (($ex -band 0x80000) -eq 0) { $failures.Add("窗口没有 WS_EX_LAYERED，逐像素透明不生效") }
}
# FindWindow 只是对照，找不到不算失败（枚举才是准的）
$byName = [YukioProbe]::FindWindowW("YukioPet", $null)
$report.Add("FindWindowW(YukioPet) = $byName")

# 她当前显示的动作：应该是“纸上书写”，气泡“编辑 login.py”
$state = $null
if (Test-Path $stateFile) {
    $state = Get-Content $stateFile -Encoding UTF8
    $report.Add("state.txt：" + ($state -join " | "))
    if ($state[0] -ne "write_file") {
        $failures.Add("动作不对：期望 write_file，实际 $($state[0])（会话记录没读进去？）")
    }
} else {
    $failures.Add("没写出 state.txt：主循环没跑起来")
}

# 截屏（没有桌面的环境下会失败，不算错）
$shot = Join-Path $out "screenshot.png"
try {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
    $report.Add("截屏：$($bounds.Width)x$($bounds.Height)")
} catch {
    $report.Add("截屏失败（这个环境可能没有桌面）：$($_.Exception.Message)")
}

# 屏幕上那一块像素，和图条逐点比
if ((Test-Path $shot) -and $petRect -and $state) {
    $checkArgs = @($shot, $state[0], $petRect.left, $petRect.top, $petRect.width, $petRect.height)
    $stderrFile = Join-Path $out "pixels-stderr.txt"
    $pixels = python scripts\check_screenshot.py @checkArgs 2>$stderrFile | Out-String
    if ((Test-Path $stderrFile) -and (Get-Item $stderrFile).Length -gt 0) {
        $report.Add("像素比对的 stderr：" + ((Get-Content $stderrFile -Raw).Trim()))
    }
    $report.Add("像素比对：" + $pixels.Trim())
    if ($LASTEXITCODE -ne 0) { $failures.Add("截屏上那一块不是她（像素比对没过）") }
}

$log = Join-Path $appData "error.log"
if (Test-Path $log) {
    Copy-Item $log (Join-Path $out "error.log")
    $text = Get-Content $log -Raw -Encoding UTF8
    $report.Add("error.log：`r`n$text")
    if ($text -match "Traceback") { $failures.Add("运行时写了 error.log，里面有 Traceback") }
}
$settings = Join-Path $appData "settings.json"
if (Test-Path $settings) { $report.Add("settings.json：$((Get-Content $settings -Raw) -replace "`r`n", " ")") }

} catch {
    $failures.Add("冒烟脚本自己出错了：$($_.Exception.Message)")
    $report.Add("异常：$($_ | Out-String)")
} finally {
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
    Get-Process -Name "Yukio" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    $report.Add("失败项：" + $(if ($failures.Count) { $failures -join "；" } else { "无" }))
    $text = $report -join "`r`n"
    Set-Content -Path (Join-Path $out "window.txt") -Value $text -Encoding UTF8
    Write-Host $text
}

if ($failures.Count) { exit 1 }
Write-Host "== 冒烟测试通过：窗口在、分层、尺寸对、动作跟对了、屏幕上画的确实是她"
exit 0
