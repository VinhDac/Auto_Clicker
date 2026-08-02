@echo off
REM ============================================================
REM  Dong goi Auto Clicker -> dist\AutoClicker\  (kieu --onedir)
REM
REM  VI SAO --onedir CHU KHONG PHAI --onefile:
REM    Ban gop-1-file bi Windows Defender bao nham la
REM    Trojan:Win32/Wacatac.H!ml va xoa ngay khi tai ve.
REM    Nguyen nhan: kieu 1-file phai tu giai nen ra thu muc tam
REM    khi chay -> Defender coi la hanh vi dang ngo.
REM    Da quet kiem chung: onefile bi bat, onedir sach.
REM
REM  Chay tu THU MUC GOC:   tools\build.bat
REM ============================================================
cd /d "%~dp0.."

echo [1/4] Dong ung dung neu dang chay...
taskkill /IM AutoClicker.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
if exist dist\AutoClicker rmdir /S /Q dist\AutoClicker

echo [2/4] Dang build...
python -m PyInstaller ^
  --onedir --windowed --name AutoClicker --noconfirm --clean ^
  --icon assets\logo.ico ^
  --exclude-module cv2 --exclude-module numpy --exclude-module mss --exclude-module PIL ^
  --add-data "data\mods_poe1.txt;." ^
  --add-data "data\mods_poe2.txt;." ^
  --add-data "assets\logo.ico;." ^
  --hidden-import plyer.platforms.win.notification ^
  auto_clicker_gui.py

if errorlevel 1 (
    echo.
    echo *** BUILD THAT BAI ***
    pause
    exit /b 1
)

echo [3/4] Them file huong dan...
> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo AUTO CLICKER cho Path of Exile
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo ==============================
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo CACH DUNG: bam dup vao AutoClicker.exe
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo LUU Y: giu nguyen ca thu muc nay, dung tach rieng file .exe ra.
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClicker\DOC-TRUOC-KHI-CHAY.txt echo Huong dan day du: https://github.com/VinhDac/Auto_Clicker

echo [4/4] Nen thanh .zip de phat hanh...
if exist AutoClicker-windows.zip del /F /Q AutoClicker-windows.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\AutoClicker' -DestinationPath 'AutoClicker-windows.zip' -CompressionLevel Optimal -Force"

echo.
echo Xong!
echo    Thu muc : dist\AutoClicker\
echo    Ban phat hanh: AutoClicker-windows.zip
echo.
pause
