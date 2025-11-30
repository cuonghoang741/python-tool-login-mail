@echo off
chcp 65001 >nul
title Install Python 3.11 for Tool Voice Cloning

echo ========================================
echo   Install Python 3.11
echo ========================================
echo.
echo This will install Python 3.11 required for Tool Voice Cloning.
echo Installing automatically...
echo.

REM Check if winget is available
where winget >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: winget is not available on this system.
    echo.
    echo Please install Python 3.11 manually:
    echo 1. Open browser and go to: https://www.python.org/downloads/
    echo 2. Download Python 3.11.x (latest 3.11 version)
    echo 3. Run the installer
    echo 4. IMPORTANT: Check "Add Python to PATH" during installation
    echo 5. Click "Install Now"
    echo 6. After installation, restart this script to verify
    echo.
    echo Or download directly from:
    echo https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    timeout /t 5 >nul
    
    REM Try to open browser
    start https://www.python.org/downloads/
    exit /b 1
)

REM Check if Python 3.11 is already installed
echo Checking for Python 3.11...
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    echo.
    echo Python 3.11 is already installed!
    py -3.11 --version
    echo.
    echo You can now run ToolVoiceCloning.exe
    echo.
    timeout /t 3 >nul
    exit /b 0
)

echo Python 3.11 is not installed.
echo.
echo Installing Python 3.11 using winget...
echo This may take a few minutes...
echo.

REM Install with all auto-accept flags and force
echo Y | winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements --force

if errorlevel 1 (
    echo.
    echo ========================================
    echo Installation failed!
    echo ========================================
    echo.
    echo Please try one of these options:
    echo.
    echo Option 1: Manual installation
    echo   1. Download from: https://www.python.org/downloads/
    echo   2. Run installer and check "Add Python to PATH"
    echo   3. Restart this script to verify
    echo.
    echo Option 2: Download direct installer
    echo   https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    timeout /t 5 >nul
    
    REM Try to open browser
    start https://www.python.org/downloads/
    exit /b 1
)

echo.
echo ========================================
echo Installation completed!
echo ========================================
echo.
echo IMPORTANT: You may need to:
echo 1. Close and reopen this window, OR
echo 2. Restart your computer
echo.
echo Then run ToolVoiceCloning.exe again.
echo.
timeout /t 3 >nul


