@echo off
REM Build Tool Voice Cloning & Synthesis to Windows EXE
REM Single file to build the application

echo ========================================
echo Building Tool Voice Cloning ^& Synthesis
echo ========================================
echo.

REM Check Python 3.11
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found. Please install: winget install Python.Python.3.11
    pause
    exit /b 1
)

REM Create isolated virtual environment
set "VOICE_ENV=venv_voice"
echo [INFO] Creating virtual environment with Python 3.11...
py -3.11 -m venv "%VOICE_ENV%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate env (helps when running manually afterward)
echo [INFO] Activating virtual environment...
call "%VOICE_ENV%\Scripts\activate.bat"

REM Upgrade pip/setuptools/wheel to avoid build issues
echo [INFO] Upgrading pip/setuptools/wheel...
"%VOICE_ENV%\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 (
    echo [ERROR] Failed to run ensurepip
    pause
    exit /b 1
)
"%VOICE_ENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip/setuptools/wheel
    pause
    exit /b 1
)

REM Install project requirements
echo [INFO] Installing Python requirements from requirements_voice.txt...
"%VOICE_ENV%\Scripts\python.exe" -m pip install -r requirements_voice.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    echo         - Kiem tra ket noi internet
    echo         - Dam bao da cai Microsoft Visual C^^++ Build Tools
    echo         - Thu chay: "%VOICE_ENV%\Scripts\python.exe" -m pip install -r requirements_voice.txt
    pause
    exit /b 1
)

REM Install PyInstaller inside the virtual environment
echo [INFO] Ensuring PyInstaller is available...
"%VOICE_ENV%\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)

REM Kill existing process if running
echo [INFO] Checking for running ToolVoiceCloning.exe...
taskkill /F /IM ToolVoiceCloning.exe >nul 2>&1
if errorlevel 1 (
    echo [INFO] No running process found.
) else (
    echo [INFO] Closed running ToolVoiceCloning.exe
    timeout /t 2 /nobreak >nul
)
echo [INFO] Killing stray python.exe processes to release file locks...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Clean old builds
echo [INFO] Cleaning old builds...
if exist dist (
    echo [INFO] Removing dist directory...
    rmdir /s /q dist
    if exist dist (
        echo [WARN] Dist removal failed, retrying...
        timeout /t 1 /nobreak >nul
        rmdir /s /q dist
    )
)
if exist build (
    echo [INFO] Removing build directory...
    rmdir /s /q build
    if exist build (
        echo [WARN] Build removal failed, retrying...
        timeout /t 1 /nobreak >nul
        rmdir /s /q build
    )
)

REM Build
echo [INFO] Building executable using tool_voices.spec...
echo This may take several minutes...
echo.

"%VOICE_ENV%\Scripts\python.exe" -m PyInstaller --clean --noconfirm tool_voices.spec
if errorlevel 1 (
    echo [WARN] Clean build failed, retrying without --clean...
    "%VOICE_ENV%\Scripts\python.exe" -m PyInstaller --noconfirm tool_voices.spec
    if errorlevel 1 (
        echo [ERROR] Build failed completely!
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo Build completed!
echo ========================================
echo.
echo EXE location: dist\ToolVoiceCloning\ToolVoiceCloning.exe
echo.
pause
