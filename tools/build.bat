@echo off
REM ============================================================
REM  Dong goi ban GIAO DIEN WEB -> dist\AutoClickerWeb\  (kieu --onedir)
REM
REM  Khac ban tkinter (tools\build.bat) o 3 diem:
REM    1. Phai chay "npm run build" TRUOC de sinh webui\dist, roi nhet vao goi.
REM    2. Diem vao la app_web.py (pywebview).
REM    3. VAN phai keo theo overlays.py + overlay_ui.py + tkinter:
REM       ba overlay chon-tren-man-hinh (crosshair / khung Abyss / luoi kho do)
REM       la cua so trong suot phu len game, WebView2 khong lam duoc, nen chung
REM       chay bang tkinter trong TIEN TRINH CON. PyInstaller khong tu thay
REM       overlays.py vi no duoc import muon trong ham -> phai --hidden-import.
REM
REM  VAN GIU --onedir: ban gop-1-file tung bi Defender bao nham
REM  Trojan:Win32/Wacatac.H!ml va xoa ngay khi tai ve. Da quet kiem chung.
REM
REM  PHAI dung Python trong .venv cua du an: goi quantconnect-stubs o Python
REM  global chiem namespace "Microsoft" lam pywebview chet ngay luc khoi dong.
REM
REM  Chay tu THU MUC GOC:   tools\build_web.bat
REM ============================================================
cd /d "%~dp0.."

set PY=.venv\Scripts\python.exe
if not exist %PY% (
    echo *** Khong thay .venv — chay truoc:  python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [1/5] Dong ung dung neu dang chay...
taskkill /IM AutoClickerWeb.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
if exist dist\AutoClickerWeb rmdir /S /Q dist\AutoClickerWeb

echo [2/5] Build giao dien web (vite)...
pushd webui
call npm run build
if errorlevel 1 (
    popd
    echo *** BUILD GIAO DIEN THAT BAI ***
    pause
    exit /b 1
)
popd

echo [3/5] Dang dong goi Python...
%PY% -m PyInstaller ^
  --onedir --windowed --name AutoClickerWeb --noconfirm --clean ^
  --icon assets\logo.ico ^
  --exclude-module cv2 --exclude-module numpy --exclude-module mss ^
  --exclude-module PIL.AvifImagePlugin --exclude-module PIL.ImageFont ^
  --exclude-module PIL.WebPImagePlugin --exclude-module PIL.ImageCms ^
  --exclude-module PIL.ImageTk ^
  --add-data "webui\dist;webui\dist" ^
  --add-data "data\mods_poe1.txt;." ^
  --add-data "data\mods_poe2.txt;." ^
  --add-data "assets\logo.ico;." ^
  --hidden-import overlays ^
  --hidden-import khung_cua_so ^
  --hidden-import overlay_ui ^
  --hidden-import plyer.platforms.win.notification ^
  --hidden-import winrt.windows.foundation ^
  --hidden-import winrt.windows.foundation.collections ^
  --hidden-import winrt.windows.globalization ^
  --hidden-import winrt.windows.graphics.imaging ^
  --hidden-import winrt.windows.media.ocr ^
  --hidden-import winrt.windows.storage.streams ^
  app_web.py

if errorlevel 1 (
    echo.
    echo *** BUILD THAT BAI ***
    pause
    exit /b 1
)

echo [4/5] Them file huong dan...
> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo AUTO CLICKER cho Path of Exile (giao dien moi)
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo =============================================
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo CACH DUNG: bam dup vao AutoClickerWeb.exe
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo LUU Y: giu nguyen ca thu muc nay, dung tach rieng file .exe ra.
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo Can Microsoft Edge WebView2 Runtime (Windows 10/11 co san cung Edge).
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo.
>> dist\AutoClickerWeb\DOC-TRUOC-KHI-CHAY.txt echo Huong dan day du: https://github.com/VinhDac/Auto_Clicker

echo [5/5] Nen thanh .zip de phat hanh...
if exist AutoClickerWeb-windows.zip del /F /Q AutoClickerWeb-windows.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\AutoClickerWeb' -DestinationPath 'AutoClickerWeb-windows.zip' -CompressionLevel Optimal -Force"

echo.
echo Xong!
echo    Thu muc      : dist\AutoClickerWeb\
echo    Ban phat hanh: AutoClickerWeb-windows.zip
echo.
pause
