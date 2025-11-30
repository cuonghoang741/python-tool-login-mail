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

REM 6. Build launcher đơn giản (không cần TTS)
echo [6/8] Build launcher .exe bằng PyInstaller (tool_voices_launcher.spec)...
python -m PyInstaller --clean --noconfirm tool_voices_launcher.spec
if errorlevel 1 (
    echo.
    echo ========================================
    echo [ERROR] Build launcher thất bại!
    echo Kiểm tra:
    echo 1. Đã đóng tất cả ToolVoiceCloning.exe đang chạy chưa
    echo 2. Thử chạy lại với quyền Administrator
    echo ========================================
    echo.
    pause
    exit /b 1
)
echo [OK] Đã build launcher thành công
echo.

REM 7. Copy venv_voice vào dist
echo [7/8] Đóng gói venv_voice vào thư mục dist...
if not exist "dist\ToolVoiceCloning" (
    echo [ERROR] Thư mục dist\ToolVoiceCloning không tồn tại!
    pause
    exit /b 1
)

if not exist "venv_voice" (
    echo [ERROR] venv_voice không tồn tại!
    pause
    exit /b 1
)

echo Đang copy venv_voice (quá trình này có thể mất vài phút)...
xcopy /E /I /Y "venv_voice" "dist\ToolVoiceCloning\venv_voice" >nul
if errorlevel 1 (
    echo [WARNING] Có lỗi khi copy venv_voice, thử lại...
    timeout /t 2 /nobreak >nul
    xcopy /E /I /Y "venv_voice" "dist\ToolVoiceCloning\venv_voice"
    if errorlevel 1 (
        echo [ERROR] Không thể copy venv_voice!
        pause
        exit /b 1
    )
)
echo [OK] Đã copy venv_voice
echo.

REM 8. Copy tool_voices và các file cần thiết
echo [8/8] Copy tool_voices và các file cần thiết...
xcopy /E /I /Y "tool_voices" "dist\ToolVoiceCloning\tool_voices" >nul
if exist "config" (
    xcopy /E /I /Y "config" "dist\ToolVoiceCloning\config" >nul
)
if exist "voices" (
    xcopy /E /I /Y "voices" "dist\ToolVoiceCloning\voices" >nul
)
if exist "outputs" (
    if not exist "dist\ToolVoiceCloning\outputs" mkdir "dist\ToolVoiceCloning\outputs"
)
if exist "logs" (
    if not exist "dist\ToolVoiceCloning\logs" mkdir "dist\ToolVoiceCloning\logs"
)
echo [OK] Đã copy các file cần thiết
echo.

echo.
echo ========================================
echo  BUILD THÀNH CÔNG!
echo ========================================
echo.
echo Cấu trúc thư mục dist\ToolVoiceCloning:
echo   - ToolVoiceCloning.exe (launcher)
echo   - venv_voice\ (virtual environment với TTS)
echo   - tool_voices\ (source code)
echo   - config\ (nếu có)
echo   - voices\ (nếu có)
echo.
echo Bạn có thể phân phối toàn bộ thư mục dist\ToolVoiceCloning
echo cho người dùng khác. Họ chỉ cần double-click ToolVoiceCloning.exe
echo để chạy ứng dụng.
echo.
pause