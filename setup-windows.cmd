@echo off
setlocal
set "PYTHONUTF8=1"
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    py -3.12 -B "%~dp0scripts\setup_windows.py" %*
    exit /b
)
py -3 --version >nul 2>&1
if not errorlevel 1 (
    py -3 -B "%~dp0scripts\setup_windows.py" %*
    exit /b
)
python --version >nul 2>&1
if not errorlevel 1 (
    python -B "%~dp0scripts\setup_windows.py" %*
    exit /b
)
echo Python not found. Install Python 3.12 from https://www.python.org/downloads/windows/ and reopen your terminal.
exit /b 2
