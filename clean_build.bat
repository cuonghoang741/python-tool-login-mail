@echo off
echo Cleaning build environment...

REM Kill any running instances
echo Stopping running processes...
taskkill /f /im GoogleFlowTool.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im chrome.exe >nul 2>&1
taskkill /f /im chromedriver.exe >nul 2>&1

REM Wait for processes to terminate
echo Waiting for processes to close...
timeout /t 3 /nobreak >nul

REM Remove build directories
echo Removing build directories...
if exist dist (
    echo Removing dist...
    rmdir /s /q dist
)

if exist build (
    echo Removing build...
    rmdir /s /q build
)

REM Remove Python cache
echo Removing Python cache...
if exist __pycache__ rmdir /s /q __pycache__
if exist tabs\__pycache__ rmdir /s /q tabs\__pycache__

REM Remove temporary files
echo Removing temporary files...
if exist *.pyc del /q *.pyc
if exist tabs\*.pyc del /q tabs\*.pyc

echo.
echo Cleanup completed!
echo You can now run build_windows.bat
echo.
pause
























