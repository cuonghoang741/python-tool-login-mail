@echo off
chcp 65001 >nul
title Tool Voice Cloning - Install and Run
echo ========================================
echo    Tool Voice Cloning ^& Synthesis
echo    Install and Run
echo ========================================
echo.

REM Lấy đường dẫn thư mục hiện tại
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

REM Kiểm tra Python 3.9-3.11
echo [1/5] Kiểm tra Python...
echo.

REM Thử các phiên bản Python từ 3.11 xuống 3.9
set "PYTHON_CMD="
for /L %%v in (11,-1,9) do (
    py -3.%%v --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3.%%v"
        goto :found_python
    )
    python3.%%v --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python3.%%v"
        goto :found_python
    )
)

REM Thử python hoặc python3 chung chung
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"
    echo %PYTHON_VERSION% | findstr /R "^3\.[9-9][0-1]$" >nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
        goto :found_python
    )
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%i in ('python3 --version 2^>^&1') do set "PYTHON_VERSION=%%i"
    echo %PYTHON_VERSION% | findstr /R "^3\.[9-9][0-1]$" >nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python3"
        goto :found_python
    )
)

:found_python
if "%PYTHON_CMD%"=="" (
    echo [ERROR] Không tìm thấy Python 3.9-3.11!
    echo.
    echo Vui lòng cài đặt Python 3.9, 3.10 hoặc 3.11 từ:
    echo https://www.python.org/downloads/
    echo.
    echo Hoặc sử dụng winget:
    echo winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)

echo [OK] Tìm thấy Python:
%PYTHON_CMD% --version
echo.

REM Kiểm tra pip
echo [2/5] Kiểm tra pip...
%PYTHON_CMD% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip không hoạt động!
    echo Đang cài đặt pip...
    %PYTHON_CMD% -m ensurepip --upgrade
)
echo [OK] pip đã sẵn sàng
echo.

REM Tạo virtual environment nếu chưa có
echo [3/5] Thiết lập môi trường ảo...
if not exist "venv_voice" (
    echo Đang tạo virtual environment...
    %PYTHON_CMD% -m venv venv_voice
    if errorlevel 1 (
        echo [ERROR] Không thể tạo virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Đã tạo virtual environment
) else (
    echo [OK] Virtual environment đã tồn tại
)
echo.

REM Kích hoạt virtual environment và cài đặt dependencies
echo [4/5] Cài đặt dependencies...
call venv_voice\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Không thể kích hoạt virtual environment!
    pause
    exit /b 1
)

REM Nâng cấp pip
python -m pip install --upgrade pip --quiet

REM Cài đặt dependencies
if exist "requirements_voice.txt" (
    echo Đang cài đặt các thư viện cần thiết...
    echo (Quá trình này có thể mất vài phút...)
    echo.
    python -m pip install -r requirements_voice.txt
    if errorlevel 1 (
        echo [ERROR] Cài đặt dependencies thất bại!
        pause
        exit /b 1
    )
    echo [OK] Đã cài đặt tất cả dependencies
) else (
    echo [WARNING] Không tìm thấy requirements_voice.txt
    echo Đang cài đặt dependencies cơ bản...
    python -m pip install PySide6 torch torchaudio TTS numpy soundfile transformers==4.36.2
)
echo.

REM Chạy ứng dụng
echo [5/5] Khởi động ứng dụng...
echo ========================================
echo    Đang mở Tool Voice Cloning...
echo ========================================
echo.

python -m tool_voices

REM Xử lý sau khi đóng ứng dụng
echo.
echo ========================================
if errorlevel 1 (
    echo    Có lỗi xảy ra!
    echo ========================================
    echo.
    echo Các khả năng:
    echo 1. Thiếu thư viện Python
    echo 2. Lỗi trong code ứng dụng
    echo 3. Python không được cài đặt đúng
    echo.
) else (
    echo    Ứng dụng đã đóng thành công!
    echo ========================================
    echo.
)

echo Nhấn phím bất kỳ để thoát...
pause >nul

