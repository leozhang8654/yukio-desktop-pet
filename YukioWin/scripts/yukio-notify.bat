@echo off
REM Deep Code 的 notify 脚本（批处理版）。能找到 python 就用旁边那个 .py，
REM 找不到就退而求其次，只写一条“这一轮结束了”。
setlocal
if not defined YUKIO_HOME set "YUKIO_HOME=%LOCALAPPDATA%\Yukio"
where python >nul 2>nul && (
  python "%~dp0yukio-notify.py"
  exit /b 0
)
if not exist "%YUKIO_HOME%" mkdir "%YUKIO_HOME%" >nul 2>nul
if /i "%STATUS%"=="failed" (
  >>"%YUKIO_HOME%\inbox.jsonl" echo {"kind":"task_failed","session":"deepcode-notify"}
) else (
  >>"%YUKIO_HOME%\inbox.jsonl" echo {"kind":"final_answer","session":"deepcode-notify"}
  >>"%YUKIO_HOME%\inbox.jsonl" echo {"kind":"task_end","session":"deepcode-notify"}
)
exit /b 0
