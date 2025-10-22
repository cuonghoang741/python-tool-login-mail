@echo off
echo Building GoogleFlowTool for Windows...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
py -m venv venv
if errorlevel 1 (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

REM (Optional) Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
venv\Scripts\python.exe -m ensurepip --upgrade
if errorlevel 1 (
    echo Error: Failed to run ensurepip
    pause
    exit /b 1
)
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Error: Failed to upgrade pip
    pause
    exit /b 1
)

REM Install requirements
echo Installing requirements...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install requirements
    pause
    exit /b 1
)

REM Install PyInstaller
echo Installing PyInstaller...
venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 (
    echo Error: Failed to install PyInstaller
    pause
    exit /b 1
)

REM Clean previous builds
echo Cleaning previous builds...
echo Waiting for any running processes to close...

REM Kill any running instances of the application
taskkill /f /im GoogleFlowTool.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1

REM Wait a moment for processes to fully terminate
timeout /t 2 /nobreak >nul

REM Force remove directories with retry mechanism
if exist dist (
    echo Removing dist directory...
    rmdir /s /q dist
    if exist dist (
        echo Retrying to remove dist directory...
        timeout /t 1 /nobreak >nul
        rmdir /s /q dist
    )
)

if exist build (
    echo Removing build directory...
    rmdir /s /q build
    if exist build (
        echo Retrying to remove build directory...
        timeout /t 1 /nobreak >nul
        rmdir /s /q build
    )
)

REM Build executable using spec file
echo Building executable using GoogleFlowTool.spec...

REM Try building with clean flag first
venv\Scripts\python.exe -m PyInstaller --clean --noconfirm GoogleFlowTool.spec
if errorlevel 1 (
    echo Build with --clean failed, trying without --clean...
    
    REM If clean build fails, try without clean flag
    venv\Scripts\python.exe -m PyInstaller --noconfirm GoogleFlowTool.spec
    if errorlevel 1 (
        echo Error: Build failed completely
        echo.
        echo Troubleshooting tips:
        echo 1. Close all instances of GoogleFlowTool.exe
        echo 2. Close any Python processes
        echo 3. Restart your computer if the problem persists
        echo 4. Try running as Administrator
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Executable location: dist\GoogleFlowTool\GoogleFlowTool.exe
echo.
echo You can now run the application by double-clicking the .exe file
echo or by running: dist\GoogleFlowTool\GoogleFlowTool.exe
echo.
echo Note: The first run may take longer as it initializes the application.
echo.
pause
