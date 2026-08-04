@echo off
REM ============================================================
REM  Cai thu vien can thiet de chay Auto Clicker tu MA NGUON.
REM  (Neu chi muon DUNG app: tai file .exe o muc Releases tren
REM   GitHub - khong can Python, khong can chay file nay.)
REM ============================================================
cd /d "%~dp0.."
title Auto Clicker - Setup

echo ============================================
echo   Cai dat Auto Clicker
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] May chua co Python.
    echo     Tai tai https://www.python.org roi chay lai file nay.
    echo.
    pause
    exit /b 1
)

echo Dang cai thu vien...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo *** Cai that bai ***
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Xong! Chay ung dung bang lenh:
echo       .venv\Scripts\python.exe app_web.py
echo ============================================
echo.
pause
