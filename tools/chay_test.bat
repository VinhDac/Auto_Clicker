@echo off
REM ============================================================
REM  Chay toan bo bai test cua Auto Clicker.
REM
REM  Bam dup file nay, hoac chay tu THU MUC GOC:  tools\chay_test.bat
REM  Them tham so --full de chay ca bai DIEU KHIEN CHUOT THAT (~30s):
REM      tools\chay_test.bat --full
REM
REM  NEN CHAY TRUOC MOI LAN BUILD.
REM ============================================================
cd /d "%~dp0.."
chcp 65001 >nul
python tests\chay_tat_ca.py %*
echo.
if errorlevel 1 (
    echo *** CO BAI TEST SAI - dung build cho den khi sua xong ***
) else (
    echo Tat ca dat. Co the build.
)
echo.
pause
