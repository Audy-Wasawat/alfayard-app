@echo off
cd /d "%~dp0"

set "TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe"

REM Prefer Anaconda Python (has all packages), fallback to py launcher
set "PY=C:\Users\ASUS\anaconda3\python.exe"
if not exist "%PY%" set "PY=py"

echo Using Python: %PY%
echo Installing required libraries (first run may take a while)...
"%PY%" -m pip install --quiet --disable-pip-version-check openpyxl pillow pytesseract google-generativeai reportlab

echo Starting program...
"%PY%" app.py

echo.
echo (Press any key to close this window)
pause >nul
