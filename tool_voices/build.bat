@echo off
REM IMPORTANT: Keep this file in plain ASCII to avoid encoding issues on some Windows setups.
chcp 65001 >nul
title Build Tool Voice Cloning (PyInstaller + CUDA)

echo ========================================
echo    BUILD Tool Voice Cloning (.exe)
echo    (with GPU/CUDA Support)
echo ========================================
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

REM Check for corrupted venv (missing pip)
REM Check for corrupted venv (missing pip)
if not exist "venv_voice\Scripts\python.exe" goto :create_venv

echo Checking venv integrity...
venv_voice\Scripts\python.exe -m pip --version >nul 2>&1
if not errorlevel 1 goto :create_venv

echo [WARN] venv_voice check failed (pip missing). Removing corrupted environment...
rmdir /s /q "venv_voice"
if exist "venv_voice" (
    echo [ERROR] Could not delete venv_voice. Please manually delete the folder 'venv_voice' and retry.
    pause
    exit /b 1
)

:create_venv

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
    echo.
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

REM Install PyTorch with CUDA support explicitly
echo Installing PyTorch with CUDA support...
REM First uninstall any existing torch versions to prevent conflicts (e.g. 2.8.0 cpu vs 2.6.0 cuda)
venv_voice\Scripts\python.exe -m pip uninstall -y torch torchaudio torchvision

venv_voice\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
if errorlevel 1 (
    echo Error: Failed to install PyTorch CUDA
    pause
    exit /b 1
)

REM Install other requirements
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

REM Install auth dependencies (required for tool_launcher.py)
echo Installing auth dependencies (requests)...
venv_voice\Scripts\python.exe -m pip install requests
if errorlevel 1 (
    echo Error: Failed to install requests
    pause
    exit /b 1
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

REM Copy venv_voice to dist first
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

REM Cleanup venv IN DIST FOLDER to reduce size (do NOT touch source venv)
echo Cleaning unnecessary files from dist venv...
set "VENV_DIST=dist\ToolVoiceCloning\venv_voice"
for /d /r "%VENV_DIST%" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
if exist "%VENV_DIST%\Include" rd /s /q "%VENV_DIST%\Include"
if exist "%VENV_DIST%\Lib\site-packages\pip" rd /s /q "%VENV_DIST%\Lib\site-packages\pip"

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
    echo Warning: setup.bat not found
)
echo.

REM Copy VC++ Redist DLLs for portability (fix "Failed to load Python DLL" on clean Windows)
echo Copying VC++ Redist DLLs...
if exist "C:\Windows\System32\vcruntime140.dll" (
    copy /Y "C:\Windows\System32\vcruntime140.dll" "dist\ToolVoiceCloning\vcruntime140.dll" >nul
    if exist "dist\ToolVoiceCloning\_internal" copy /Y "C:\Windows\System32\vcruntime140.dll" "dist\ToolVoiceCloning\_internal\vcruntime140.dll" >nul
)
if exist "C:\Windows\System32\msvcp140.dll" (
    copy /Y "C:\Windows\System32\msvcp140.dll" "dist\ToolVoiceCloning\msvcp140.dll" >nul
    if exist "dist\ToolVoiceCloning\_internal" copy /Y "C:\Windows\System32\msvcp140.dll" "dist\ToolVoiceCloning\_internal\msvcp140.dll" >nul
)
if exist "C:\Windows\System32\vcruntime140_1.dll" (
    copy /Y "C:\Windows\System32\vcruntime140_1.dll" "dist\ToolVoiceCloning\vcruntime140_1.dll" >nul
    if exist "dist\ToolVoiceCloning\_internal" copy /Y "C:\Windows\System32\vcruntime140_1.dll" "dist\ToolVoiceCloning\_internal\vcruntime140_1.dll" >nul
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
