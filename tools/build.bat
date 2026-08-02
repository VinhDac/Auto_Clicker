@echo off
REM ============================================================
REM  Dong goi Auto Clicker thanh 1 file .exe chay doc lap
REM  Chay tu THU MUC GOC cua du an:   tools\build.bat
REM ============================================================
cd /d "%~dp0.."

echo [1/3] Dong ung dung neu dang chay...
taskkill /IM AutoClicker.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
if exist dist\AutoClicker.exe del /F /Q dist\AutoClicker.exe

echo [2/3] Dang build (mat khoang 15-30 giay)...
python -m PyInstaller ^
  --onefile --windowed --name AutoClicker --noconfirm --clean ^
  --exclude-module cv2 --exclude-module numpy --exclude-module mss --exclude-module PIL ^
  --add-data "data\mods_poe1.txt;." ^
  --add-data "data\mods_poe2.txt;." ^
  --hidden-import plyer.platforms.win.notification ^
  auto_clicker_gui.py

if errorlevel 1 (
    echo.
    echo *** BUILD THAT BAI ***
    pause
    exit /b 1
)

echo [3/3] Xong!
for %%F in (dist\AutoClicker.exe) do echo     dist\AutoClicker.exe  (%%~zF bytes^)
echo.
pause
