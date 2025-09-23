@echo off
chcp 65001 >nul
echo 🎬 Google Flow Tool Installer
echo.

REM Tạo thư mục cài đặt
set INSTALL_DIR=%USERPROFILE%\GoogleFlowTool
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo 📁 Đang cài đặt vào: %INSTALL_DIR%

REM Copy file exe
if exist "GoogleFlowTool.exe" (
    copy "GoogleFlowTool.exe" "%INSTALL_DIR%\" >nul
    echo ✅ Đã copy GoogleFlowTool.exe
) else (
    echo ❌ Không tìm thấy GoogleFlowTool.exe
    pause
    exit /b 1
)

REM Copy chrome_cache folder nếu có
if exist "chrome_cache" (
    xcopy "chrome_cache" "%INSTALL_DIR%\chrome_cache\" /E /I /Q >nul
    echo ✅ Đã copy chrome_cache
)

REM Tạo shortcut trên Desktop
set DESKTOP=%USERPROFILE%\Desktop
echo [InternetShortcut] > "%DESKTOP%\Google Flow Tool.url"
echo URL=file:///%INSTALL_DIR%\GoogleFlowTool.exe >> "%DESKTOP%\Google Flow Tool.url"
echo IconFile=%INSTALL_DIR%\GoogleFlowTool.exe >> "%DESKTOP%\Google Flow Tool.url"
echo IconIndex=0 >> "%DESKTOP%\Google Flow Tool.url"

REM Tạo shortcut trong Start Menu
set START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs
if not exist "%START_MENU%" mkdir "%START_MENU%"
echo [InternetShortcut] > "%START_MENU%\Google Flow Tool.url"
echo URL=file:///%INSTALL_DIR%\GoogleFlowTool.exe >> "%START_MENU%\Google Flow Tool.url"
echo IconFile=%INSTALL_DIR%\GoogleFlowTool.exe >> "%START_MENU%\Google Flow Tool.url"
echo IconIndex=0 >> "%START_MENU%\Google Flow Tool.url"

echo.
echo ✅ Cài đặt hoàn tất!
echo 📁 Thư mục cài đặt: %INSTALL_DIR%
echo 🖥️  Shortcut đã tạo trên Desktop và Start Menu
echo.
echo 🚀 Bạn có thể chạy tool bằng cách:
echo   1. Double-click shortcut trên Desktop
echo   2. Hoặc chạy trực tiếp: %INSTALL_DIR%\GoogleFlowTool.exe
echo.
pause
