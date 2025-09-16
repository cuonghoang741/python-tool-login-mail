@echo off
title Gmail Login Tool
echo ========================================
echo    Gmail Login Tool - Starting...
echo ========================================
echo.

REM Kiểm tra Python có được cài đặt không
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python chua duoc cai dat!
    echo Vui long cai dat Python tu: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Hiển thị thông tin Python
echo Python version:
python --version
echo.

REM Kiểm tra file gmail_login_tool.py có tồn tại không
if not exist "gmail_login_tool.py" (
    echo ERROR: Khong tim thay file gmail_login_tool.py!
    echo Vui long dam bao file nay co trong cung thu muc.
    echo.
    pause
    exit /b 1
)

REM Chạy ứng dụng
echo Dang khoi dong Gmail Login Tool...
echo.
echo Chon phien ban:
echo 1. Browser Login (Khuyen nghi - ho tro 2FA)
echo 2. Password Login (Truyen thong)
echo.
set /p choice="Nhap lua chon (1 hoac 2): "

if "%choice%"=="1" (
    echo Dang khoi dong Browser Login...
    python gmail_browser_login.py
) else if "%choice%"=="2" (
    echo Dang khoi dong Password Login...
    python gmail_login_tool.py
) else (
    echo Lua chon khong hop le. Chay Browser Login mac dinh...
    python gmail_browser_login.py
)

REM Nếu có lỗi, hiển thị thông báo
if errorlevel 1 (
    echo.
    echo ========================================
    echo    Co loi xay ra khi chay ung dung!
    echo ========================================
    echo.
    echo Cac kha nang:
    echo 1. Thieu thu vien Python
    echo 2. File gmail_login_tool.py bi loi
    echo 3. Python khong duoc cai dat dung
    echo.
    echo Vui long kiem tra lai va thu chay lai.
    echo.
)

echo.
echo Ung dung da dong. Nhan phim bat ky de thoat...
pause >nul
