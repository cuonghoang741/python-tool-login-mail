@echo off
chcp 65001 >nul
echo ========================================
echo   Tool Voice Cloning - Setup
echo ========================================
echo.
echo This script will install Python 3.11 if not already installed.
echo Running automatically...
echo.

REM Check if Python 3.11 is already installed
echo Checking for Python 3.11...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.11 is not installed.
    echo.
    echo Installing Python 3.11 using winget...
    echo.
    
    REM Try to install using winget with auto-accept
    echo Y | winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements --force
    if errorlevel 1 (
        echo.
        echo ========================================
        echo Installation failed!
        echo ========================================
        echo.
        echo Please install Python 3.11 manually:
        echo 1. Download from: https://www.python.org/downloads/
        echo 2. Run installer and check "Add Python to PATH"
        echo 3. Restart this setup script
        echo.
        timeout /t 5 >nul
        exit /b 1
    )
    
    echo.
    echo Python 3.11 installed successfully!
    echo.
    echo IMPORTANT: You may need to restart your computer or
    echo close and reopen this window for Python to be available.
    echo.
    
    REM Refresh PATH
    call refreshenv >nul 2>&1
    
    REM Check again
    py -3.11 --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Python is installed but not yet available in PATH.
        echo Please restart your computer or close and reopen this window.
        echo.
        timeout /t 5 >nul
        exit /b 1
    )
) else (
    echo Python 3.11 is already installed!
    py -3.11 --version
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo You can now run ToolVoiceCloning.exe
echo.
timeout /t 3 >nul


