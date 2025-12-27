@echo off
REM IMPORTANT: Keep this file in plain ASCII to avoid encoding issues on some Windows setups.
REM Do NOT save this file as UTF-16.

chcp 65001 >nul
title Build Tool Voice Cloning (PyInstaller)

echo ========================================
echo    BUILD Tool Voice Cloning (.exe)
echo ========================================
echo.

REM 1. Go to script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM 2. Check Python 3.11
echo [1/6] Checking Python 3.11...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found
    echo Please install: winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)
echo [OK] Python 3.11 found
echo.

REM 3. Create or reuse venv_voice
echo [2/6] Setting up virtual environment (venv_voice)...
if not exist "venv_voice" (
    echo Creating virtual environment venv_voice...
    py -3.11 -m venv venv_voice
    if errorlevel 1 (
        echo [ERROR] Cannot create virtual environment!
        pause
        exit /b 1
    )
) else (
    echo venv_voice already exists, reusing.
)
echo.

REM 4. Activate venv_voice
echo [3/6] Activating venv_voice...
call "venv_voice\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Cannot activate venv_voice!
    pause
    exit /b 1
)
echo [OK] venv_voice activated
echo.

REM 5. Upgrade pip and install requirements + PyInstaller
echo [4/6] Installing / upgrading dependencies...
python -m ensurepip --upgrade
python -m pip install --upgrade pip setuptools wheel

if exist "requirements_voice.txt" (
    echo Installing packages from requirements_voice.txt...
    python -m pip install -r "requirements_voice.txt"
) else (
    echo [WARNING] requirements_voice.txt not found, skipping this step.
)

echo Installing PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Cannot install PyInstaller!
    pause
    exit /b 1
)
echo.

REM 6. Clean old builds
echo [5/6] Cleaning old build...

REM Kill running app (if any)
taskkill /f /im ToolVoiceCloning.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Remove old dist/build folders
if exist "dist\ToolVoiceCloning" (
    echo Removing dist\ToolVoiceCloning...
    rmdir /s /q "dist\ToolVoiceCloning"
)

if exist "build" (
    echo Removing build folder...
    rmdir /s /q "build"
)

echo.

REM 7. Build launcher (no TTS inside)
echo [6/8] Building launcher .exe with PyInstaller (tool_voices_launcher.spec)...
python -m PyInstaller --clean --noconfirm "tool_voices_launcher.spec"
if errorlevel 1 (
    echo.
    echo ========================================
    echo [ERROR] Launcher build failed!
    echo Please check:
    echo 1. All ToolVoiceCloning.exe are closed
    echo 2. Try to run this script as Administrator
    echo ========================================
    echo.
    pause
    exit /b 1
)
echo [OK] Launcher built successfully
echo.

REM 8. Copy venv_voice into dist
echo [7/8] Packing venv_voice into dist...
if not exist "dist\ToolVoiceCloning" (
    echo [ERROR] Folder dist\ToolVoiceCloning does not exist!
    pause
    exit /b 1
)

if not exist "venv_voice" (
    echo [ERROR] venv_voice does not exist!
    pause
    exit /b 1
)

echo Copying venv_voice (this may take a few minutes)...
xcopy /E /I /Y "venv_voice" "dist\ToolVoiceCloning\venv_voice" >nul
if errorlevel 1 (
    echo [WARNING] Error while copying venv_voice, retrying...
    timeout /t 2 /nobreak >nul
    xcopy /E /I /Y "venv_voice" "dist\ToolVoiceCloning\venv_voice"
    if errorlevel 1 (
        echo [ERROR] Cannot copy venv_voice!
        pause
        exit /b 1
    )
)
echo [OK] venv_voice copied
echo.

REM 9. Copy tool_voices, shared login module, and other required files
echo [8/8] Copying tool_voices, tool_launcher and other required files...
xcopy /E /I /Y "tool_voices" "dist\ToolVoiceCloning\tool_voices" >nul

REM Copy shared login module so external Python can import it
if exist "tool_launcher.py" (
    copy /Y "tool_launcher.py" "dist\ToolVoiceCloning\tool_launcher.py" >nul
)

REM Copy auth_config.json if present (so the EXE has initial config / saved login)
if exist "auth_config.json" (
    copy /Y "auth_config.json" "dist\ToolVoiceCloning\auth_config.json" >nul
)

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
echo [OK] All files copied
echo.

echo.
echo ========================================
echo  BUILD SUCCESSFUL!
echo ========================================
echo.
echo dist\ToolVoiceCloning content:
echo   - ToolVoiceCloning.exe (launcher)
echo   - venv_voice\ (virtual environment with TTS)
echo   - tool_voices\ (source code)
echo   - config\ (if exists)
echo   - voices\ (if exists)
echo   - outputs\ (if exists)
echo   - logs\ (if exists)
echo.
echo You can distribute the whole dist\ToolVoiceCloning folder
echo to other users. They only need to double-click ToolVoiceCloning.exe
echo to run the app.
echo.
pause