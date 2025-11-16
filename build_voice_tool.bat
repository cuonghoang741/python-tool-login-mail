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

REM Install PyInstaller if needed
py -3.11 -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    py -3.11 -m pip install pyinstaller
)

REM Clean old builds
echo [INFO] Cleaning old builds...
if exist "build\ToolVoiceCloning" rmdir /s /q "build\ToolVoiceCloning" 2>nul
if exist "dist\ToolVoiceCloning" rmdir /s /q "dist\ToolVoiceCloning" 2>nul

REM Build
echo [INFO] Building executable...
echo This may take several minutes...
echo.

py -3.11 -m PyInstaller tool_voices.spec --clean --noconfirm

if errorlevel 1 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed!
echo ========================================
echo.
echo EXE location: dist\ToolVoiceCloning\ToolVoiceCloning.exe
echo.
pause
