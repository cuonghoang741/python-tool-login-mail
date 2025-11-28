@echo off
chcp 65001 >nul
title Build Tool Voice Cloning (PyInstaller)

echo ========================================
echo    BUILD Tool Voice Cloning ^(.exe^)
echo ========================================
echo.

REM Lấy thư mục hiện tại (thư mục chứa file .bat)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM 1. Kiểm tra Python 3.11
echo [1/6] Kiểm tra Python 3.11...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Chưa cài Python 3.11
    echo Vui lòng cài: winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)
echo [OK] Đã tìm thấy Python 3.11
echo.

REM 2. Tạo hoặc dùng lại venv_voice
echo [2/6] Thiết lập virtual environment (venv_voice)...
if not exist "venv_voice" (
    echo Đang tạo virtual environment venv_voice...
    py -3.11 -m venv venv_voice
    if errorlevel 1 (
        echo [ERROR] Không thể tạo virtual environment!
        pause
        exit /b 1
    )
) else (
    echo venv_voice đã tồn tại, dùng lại.
)
echo.

REM 3. Kích hoạt venv_voice
echo [3/6] Kích hoạt venv_voice...
call venv_voice\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Không thể kích hoạt venv_voice!
    pause
    exit /b 1
)
echo [OK] Đã kích hoạt venv_voice
echo.

REM 4. Cập nhật pip và cài requirements + PyInstaller
echo [4/6] Cài đặt / cập nhật thư viện...
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel

if exist "requirements_voice.txt" (
    echo Đang cài đặt các thư viện trong requirements_voice.txt...
    python -m pip install -r requirements_voice.txt
) else (
    echo [WARNING] Không tìm thấy requirements_voice.txt, bỏ qua bước này.
)

echo Cài đặt PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Không thể cài PyInstaller!
    pause
    exit /b 1
)
echo.

REM 5. Dọn dẹp build cũ
echo [5/6] Dọn dẹp build cũ...

REM Tắt app đang chạy (nếu có)
taskkill /f /im ToolVoiceCloning.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Xóa thư mục dist/build liên quan
if exist "dist\ToolVoiceCloning" (
    echo Xoá dist\ToolVoiceCloning...
    rmdir /s /q "dist\ToolVoiceCloning"
)

if exist "build" (
    echo Xoá thư mục build...
    rmdir /s /q "build"
)

echo.

REM 6. Chạy PyInstaller với file spec sẵn có: tool_voices.spec
echo [6/6] Build .exe bằng PyInstaller (tool_voices.spec)...
python -m PyInstaller --clean --noconfirm tool_voices.spec
if errorlevel 1 (
    echo.
    echo ========================================
    echo [ERROR] Build thất bại!
    echo Kiểm tra:
    echo 1. Đã cài đúng các thư viện trong requirements_voice.txt chưa
    echo 2. Đã đóng tất cả ToolVoiceCloning.exe đang chạy chưa
    echo 3. Thử chạy lại với quyền Administrator
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  BUILD THÀNH CÔNG!
echo  File exe: dist\ToolVoiceCloning\ToolVoiceCloning.exe
echo ========================================
echo.
pause