@echo off
setlocal
set "PYTHONUTF8=1"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Run setup-windows.cmd first.
    exit /b 2
)
"%~dp0.venv\Scripts\python.exe" -B "%~dp0tools\verify_doc2md.py" %*
exit /b %ERRORLEVEL%
