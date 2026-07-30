@echo off
title Auto Clicker - Setup
echo ============================================
echo   Cai dat Auto Clicker cho may nay
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Chua co Python. Tai o https://www.python.org roi chay lai file nay.
    pause
    exit /b
)
echo Dang cai thu vien...
python -m pip install -r requirements.txt
echo.
echo ============================================
echo   Xong! Chay ung dung bang lenh:
echo       python auto_clicker_gui.py
echo   (Hoac vao ung dung ^> Cai dat ^> Tao shortcut o Desktop)
echo ============================================
pause
