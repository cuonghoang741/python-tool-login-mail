@echo off
echo Building VideoLengthTool for Windows...
echo.

REM Check if Python 3.11 is available
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3.11 is not installed.
    echo Please install Python 3.11, for example:
    echo   winget install Python.Python.3.11
    pause
    exit /b 1
)

REM Create virtual environment for VideoLengthTool (local to this folder)
set VENV_DIR=venv_video_length
echo Creating virtual environment "%VENV_DIR%" with Python 3.11...
py -3.11 -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo Error: Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip and install PyInstaller
echo Upgrading pip and installing PyInstaller...
"%VENV_DIR%\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 (
    echo Error: Failed to run ensurepip.
    pause
    exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Error: Failed to upgrade pip.
    pause
    exit /b 1
)
"%VENV_DIR%\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 (
    echo Error: Failed to install PyInstaller.
    pause
    exit /b 1
)

REM Install customtkinter and darkdetect (required for modern UI)
echo Installing customtkinter...
"%VENV_DIR%\Scripts\python.exe" -m pip install customtkinter darkdetect
if errorlevel 1 (
    echo Error: Failed to install customtkinter.
    pause
    exit /b 1
)

REM Clean previous builds (local to this folder)
echo Cleaning previous builds...
if exist dist (
    echo Removing dist directory...
    rmdir /s /q dist
)
if exist build (
    echo Removing build directory...
    rmdir /s /q build
)

REM Build executable (onefile, windowed)
set SCRIPT_PATH=video_length_tool.py
set APP_NAME=VideoLengthTool

echo Building executable "%APP_NAME%" from "%SCRIPT_PATH%"...
"%VENV_DIR%\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --windowed ^
  --name "%APP_NAME%" ^
  --collect-all customtkinter ^
  --hidden-import darkdetect ^
  "%SCRIPT_PATH%"

if errorlevel 1 (
    echo Error: Build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Executable location: dist\%APP_NAME%.exe
echo.
echo You can now run the application by double-clicking the .exe file.
echo.
pause





