@echo off
echo Building Tool Voice Cloning for Windows...
echo.

REM Change to parent directory (where venv_voice, requirements_voice.txt, tool_voices_launcher.spec are located)
cd /d "%~dp0\.."
echo Working directory: %CD%
echo.

REM Check if Python 3.11 is available
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3.11 is not installed
    echo Please install Python 3.11: winget install Python.Python.3.11
    pause
    exit /b 1
)

REM Create virtual environment with Python 3.11
echo Creating virtual environment with Python 3.11...
if not exist "venv_voice" (
    echo Creating portable virtual environment venv_voice with --copies...
    py -3.11 -m venv --copies venv_voice
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo.
    echo Fixing venv paths for portability...
    REM Fix pyvenv.cfg to use relative paths
    if exist "venv_voice\pyvenv.cfg" (
        REM Backup original
        copy /Y "venv_voice\pyvenv.cfg" "venv_voice\pyvenv.cfg.bak" >nul
        REM Update to use relative path (will be fixed after copy)
        powershell -Command "(Get-Content 'venv_voice\pyvenv.cfg') -replace '^home = .*', 'home = .' | Set-Content 'venv_voice\pyvenv.cfg'"
    )
) else (
    echo venv_voice already exists, reusing it.
    echo Note: If this venv was created without --copies, it may not be portable.
    echo To ensure portability, delete venv_voice and rebuild.
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv_voice\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)
echo.

REM Upgrade pip
echo Upgrading pip...
venv_voice\Scripts\python.exe -m ensurepip --upgrade
if errorlevel 1 (
    echo Error: Failed to run ensurepip
    pause
    exit /b 1
)
venv_voice\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Error: Failed to upgrade pip
    pause
    exit /b 1
)

REM Install requirements
echo Installing requirements...
if exist "requirements_voice.txt" (
    venv_voice\Scripts\python.exe -m pip install -r requirements_voice.txt
    if errorlevel 1 (
        echo Error: Failed to install requirements
        pause
        exit /b 1
    )
) else (
    echo Warning: requirements_voice.txt not found, skipping this step.
)
echo.

REM Install PyInstaller
echo Installing PyInstaller...
venv_voice\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 (
    echo Error: Failed to install PyInstaller
    pause
    exit /b 1
)
echo.

REM Clean previous builds
echo Cleaning previous builds...
echo Waiting for any running processes to close...

REM Kill any running instances of the application
taskkill /f /im ToolVoiceCloning.exe >nul 2>&1
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
echo.

REM Build executable using spec file
echo Building executable using tool_voices_launcher.spec...

REM Try building with clean flag first
venv_voice\Scripts\python.exe -m PyInstaller --clean --noconfirm tool_voices_launcher.spec
if errorlevel 1 (
    echo Build with --clean failed, trying without --clean...
    
    REM If clean build fails, try without clean flag
    venv_voice\Scripts\python.exe -m PyInstaller --noconfirm tool_voices_launcher.spec
    if errorlevel 1 (
        echo Error: Build failed completely
        echo.
        echo Troubleshooting tips:
        echo 1. Close all instances of ToolVoiceCloning.exe
        echo 2. Close any Python processes
        echo 3. Restart your computer if the problem persists
        echo 4. Try running as Administrator
        pause
        exit /b 1
    )
)
echo.

REM Copy venv_voice to dist
echo Packaging venv_voice into dist directory...
if not exist "dist\ToolVoiceCloning" (
    echo Error: dist\ToolVoiceCloning directory does not exist!
    pause
    exit /b 1
)

if not exist "venv_voice" (
    echo Error: venv_voice does not exist!
    pause
    exit /b 1
)

echo Copying venv_voice (this may take several minutes)...
xcopy /E /I /Y "venv_voice" "dist\ToolVoiceCloning\venv_voice" >nul
if errorlevel 1 (
    echo Warning: Error copying venv_voice, retrying...
    timeout /t 2 /nobreak >nul
    xcopy /E /I /Y "venv_voice" "dist\ToolVoiceCloning\venv_voice"
    if errorlevel 1 (
        echo Error: Failed to copy venv_voice!
        pause
        exit /b 1
    )
)

REM Fix venv paths for portability after copying
echo Fixing venv paths for portability...
set "VENV_DIST=dist\ToolVoiceCloning\venv_voice"
if exist "%VENV_DIST%\pyvenv.cfg" (
    REM Update pyvenv.cfg to use relative path
    powershell -Command "$content = Get-Content '%VENV_DIST%\pyvenv.cfg'; $content = $content -replace '^home = .*', 'home = .'; Set-Content '%VENV_DIST%\pyvenv.cfg' $content"
)

REM Fix Python launcher scripts to use relative paths
if exist "%VENV_DIST%\Scripts\python.exe" (
    REM The python.exe should work, but we need to ensure scripts use correct paths
    echo Venv paths fixed.
)
echo.

REM Copy tool_voices, shared login module and necessary files
echo Copying tool_voices, tool_launcher and necessary files...
xcopy /E /I /Y "tool_voices" "dist\ToolVoiceCloning\tool_voices" >nul

REM Copy shared login module so voice tool can reuse the same auth flow
if exist "tool_launcher.py" (
    copy /Y "tool_launcher.py" "dist\ToolVoiceCloning\tool_launcher.py" >nul
)

REM Copy auth_config.json if present (persisted login/config)
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
echo.

REM Copy logo and create README
echo Copying logo and creating README...
if exist "logo.ico" (
    copy /Y "logo.ico" "dist\ToolVoiceCloning\logo.ico" >nul
)
if exist "logo.png" (
    copy /Y "logo.png" "dist\ToolVoiceCloning\logo.png" >nul
)

REM Copy README template
if exist "tool_voices\README_template.txt" (
    copy /Y "tool_voices\README_template.txt" "dist\ToolVoiceCloning\README.txt" >nul
) else (
    echo Warning: README_template.txt not found, skipping README creation
)

REM Copy setup scripts
echo Copying setup scripts...
if exist "tool_voices\install_python.bat" (
    copy /Y "tool_voices\install_python.bat" "dist\ToolVoiceCloning\install_python.bat" >nul
    echo   - install_python.bat copied
) else (
    echo Warning: install_python.bat not found
)
if exist "tool_voices\setup.bat" (
    copy /Y "tool_voices\setup.bat" "dist\ToolVoiceCloning\setup.bat" >nul
    echo   - setup.bat copied
) else (
    echo Warning: setup.bat not found
)
echo.

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Directory structure in dist\ToolVoiceCloning:
echo   - ToolVoiceCloning.exe (launcher with icon)
echo   - install_python.bat (Python installer - run this first if needed)
echo   - setup.bat (alternative setup script)
echo   - README.txt (user guide)
echo   - logo.ico, logo.png (application logo)
echo   - venv_voice\ (virtual environment with TTS)
echo   - tool_voices\ (source code)
echo   - config\ (if exists)
echo   - voices\ (if exists)
echo   - outputs\ (output files directory)
echo   - logs\ (log files directory)
echo.
echo ========================================
echo IMPORTANT: PYTHON 3.11 REQUIRED
echo ========================================
echo.
echo You can distribute the entire dist\ToolVoiceCloning folder
echo to other users. They need to:
echo   1. Extract the dist\ToolVoiceCloning folder
echo   2. Run install_python.bat if Python 3.11 is not installed
echo   3. Double-click ToolVoiceCloning.exe to run
echo.
echo The install_python.bat script will automatically install
echo Python 3.11 if it's not already on the system.
echo.
pause
