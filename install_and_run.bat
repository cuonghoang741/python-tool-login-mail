@echo off
title Gmail Login Tool - Install and Run
echo ========================================
echo    Gmail Login Tool - Install and Run
echo ========================================
echo.

REM Kiểm tra Python có được cài đặt không
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python chua duoc cai dat!
    echo.
    echo Vui long cai dat Python tu: https://www.python.org/downloads/
    echo Sau khi cai dat xong, chay lai file nay.
    echo.
    pause
    exit /b 1
)

echo Python da duoc cai dat:
python --version
echo.

REM Kiểm tra pip có hoạt động không
pip --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: pip khong hoat dong. Thu vien co the da co san.
    echo.
) else (
    echo pip version:
    pip --version
    echo.
)

REM Kiểm tra file requirements.txt
if exist "requirements.txt" (
    echo Tim thay requirements.txt...
    echo Cac thu vien can thiet:
    type requirements.txt
    echo.
    echo NOTE: Cac thu vien nay da co san trong Python.
    echo Khong can cai dat them.
    echo.
) else (
    echo WARNING: Khong tim thay requirements.txt
    echo.
)

REM Kiểm tra file gmail_login_tool.py
if not exist "gmail_login_tool.py" (
    echo ERROR: Khong tim thay file gmail_login_tool.py!
    echo Vui long dam bao file nay co trong cung thu muc.
    echo.
    pause
    exit /b 1
)

echo File gmail_login_tool.py da san sang!
echo.

REM Chạy ứng dụng
echo ========================================
echo    Dang khoi dong Gmail Login Tool...
echo ========================================
echo.
echo Huong dan su dung:
echo 1. Nhap email Gmail cua ban
echo 2. Nhap App Password (khong phai mat khau thuong)
echo 3. Nhan "Dang nhap"
echo 4. Nhan "Tai Email" de xem danh sach email
echo.
echo LUU Y: Can tao App Password trong Google Account!
echo Xem huong dan trong file HUONG_DAN_SU_DUNG.md
echo.
echo ========================================
echo.

python gmail_login_tool.py

REM Xử lý sau khi đóng ứng dụng
echo.
echo ========================================
if errorlevel 1 (
    echo    Co loi xay ra!
    echo ========================================
    echo.
    echo Cac kha nang:
    echo 1. Thieu thu vien Python
    echo 2. File gmail_login_tool.py bi loi
    echo 3. Python khong duoc cai dat dung
    echo 4. Loi ket noi internet
    echo.
    echo Giai phap:
    echo 1. Kiem tra ket noi internet
    echo 2. Kiem tra App Password
    echo 3. Chay lai ung dung
    echo.
) else (
    echo    Ung dung da dong thanh cong!
    echo ========================================
    echo.
    echo Cam on ban da su dung Gmail Login Tool!
    echo.
)

echo Nhan phim bat ky de thoat...
pause >nul
