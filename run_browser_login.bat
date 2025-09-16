@echo off
title Gmail Browser Login Tool
echo ========================================
echo    Gmail Browser Login Tool - Starting...
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

REM Kiểm tra file gmail_browser_login.py có tồn tại không
if not exist "gmail_browser_login.py" (
    echo ERROR: Khong tim thay file gmail_browser_login.py!
    echo Vui long dam bao file nay co trong cung thu muc.
    echo.
    pause
    exit /b 1
)

REM Cài đặt thư viện cần thiết
echo Dang kiem tra va cai dat thu vien...
pip install selenium webdriver-manager --quiet
echo.

REM Chạy ứng dụng
echo ========================================
echo    Dang khoi dong Gmail Browser Login...
echo ========================================
echo.
echo Tinh nang:
echo - Mo browser Chrome de dang nhap that
echo - Ho tro 2FA tu dong (OTP, SMS, Authenticator)
echo - Cho toi 5 phut de xu ly 2FA
echo - Ket noi IMAP sau khi dang nhap thanh cong
echo.
echo LUU Y: Can co Chrome browser tren may!
echo.
echo ========================================
echo.

python gmail_browser_login.py

REM Nếu có lỗi, hiển thị thông báo
if errorlevel 1 (
    echo.
    echo ========================================
    echo    Co loi xay ra khi chay ung dung!
    echo ========================================
    echo.
    echo Cac kha nang:
    echo 1. Thieu thu vien Python (selenium, webdriver-manager)
    echo 2. File gmail_browser_login.py bi loi
    echo 3. Python khong duoc cai dat dung
    echo 4. Chrome browser chua duoc cai dat
    echo.
    echo Giai phap:
    echo 1. Cai dat Chrome browser
    echo 2. Chay: pip install selenium webdriver-manager
    echo 3. Kiem tra ket noi internet
    echo.
)

echo.
echo Ung dung da dong. Nhan phim bat ky de thoat...
pause >nul
