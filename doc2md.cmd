@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Run setup-windows.cmd first.
    exit /b 2
)
set "PATH=%~dp0.venv\Scripts;%PATH%"
if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" set "PATH=%ProgramFiles%\Tesseract-OCR;%PATH%"
if exist "%~dp0.venv\share\tessdata\vie.traineddata" set "TESSDATA_PREFIX=%~dp0.venv\share\tessdata"
"%~dp0.venv\Scripts\python.exe" -B "%~dp0tools\fast_doc2md.py" %*
exit /b %ERRORLEVEL%
