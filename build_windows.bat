@echo off
echo Building GoogleFlowTool for Windows...

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
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Build executable
echo Building executable...
venv\Scripts\python.exe -m PyInstaller --clean --noconfirm GoogleFlowTool.spec
if errorlevel 1 (
    echo Error: Build failed
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo Executable location: dist\GoogleFlowTool\GoogleFlowTool.exe
echo.
pause
