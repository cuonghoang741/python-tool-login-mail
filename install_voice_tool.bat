@echo off
chcp 65001 >nul
title Tool Voice Cloning & Synthesis - Installer

echo ==============================================
echo   Tool Voice Cloning ^& Synthesis - Installer
echo ==============================================
echo.

REM Thu muc cai dat trong User profile
set "INSTALL_DIR=%USERPROFILE%\ToolVoiceCloning"

if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
)

echo 📁 Dang cai dat vao: %INSTALL_DIR%
echo.

REM Kiem tra file exe da build (uu tien ban moi nhat trong dist\ToolVoiceCloning\)
if exist "dist\ToolVoiceCloning\ToolVoiceCloning.exe" (
    copy "dist\ToolVoiceCloning\ToolVoiceCloning.exe" "%INSTALL_DIR%\" >nul
    echo ✅ Da copy dist\ToolVoiceCloning\ToolVoiceCloning.exe
) else if exist "dist\ToolVoiceCloning.exe" (
    copy "dist\ToolVoiceCloning.exe" "%INSTALL_DIR%\" >nul
    echo ✅ Da copy dist\ToolVoiceCloning.exe
) else if exist "ToolVoiceCloning.exe" (
    copy "ToolVoiceCloning.exe" "%INSTALL_DIR%\" >nul
    echo ✅ Da copy ToolVoiceCloning.exe
) else (
    echo ❌ Khong tim thay file ToolVoiceCloning.exe
    echo Vui long chay .\build_voice_tool.bat truoc khi cai dat.
    echo.
    pause
    exit /b 1
)

REM Copy config mac dinh neu co
if exist "config" (
    xcopy "config" "%INSTALL_DIR%\config\" /E /I /Q /Y >nul
    echo ✅ Da copy config mac dinh
)

REM Tao thu muc voices/outputs neu chua co
if not exist "%INSTALL_DIR%\voices" (
    mkdir "%INSTALL_DIR%\voices"
)
if not exist "%INSTALL_DIR%\outputs" (
    mkdir "%INSTALL_DIR%\outputs"
)
if not exist "%INSTALL_DIR%\logs" (
    mkdir "%INSTALL_DIR%\logs"
)

REM Tao shortcut tren Desktop
set "DESKTOP=%USERPROFILE%\Desktop"
echo [InternetShortcut] > "%DESKTOP%\Tool Voice Cloning & Synthesis.url"
echo URL=file:///%INSTALL_DIR%\ToolVoiceCloning.exe >> "%DESKTOP%\Tool Voice Cloning & Synthesis.url"
echo IconFile=%INSTALL_DIR%\ToolVoiceCloning.exe >> "%DESKTOP%\Tool Voice Cloning & Synthesis.url"
echo IconIndex=0 >> "%DESKTOP%\Tool Voice Cloning & Synthesis.url"

REM Tao shortcut trong Start Menu
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
if not exist "%START_MENU%" mkdir "%START_MENU%"
echo [InternetShortcut] > "%START_MENU%\Tool Voice Cloning & Synthesis.url"
echo URL=file:///%INSTALL_DIR%\ToolVoiceCloning.exe >> "%START_MENU%\Tool Voice Cloning & Synthesis.url"
echo IconFile=%INSTALL_DIR%\ToolVoiceCloning.exe >> "%START_MENU%\Tool Voice Cloning & Synthesis.url"
echo IconIndex=0 >> "%START_MENU%\Tool Voice Cloning & Synthesis.url"

echo.
echo ✅ Cai dat hoan tat!
echo 📁 Thu muc cai dat: %INSTALL_DIR%
echo 🖥️  Shortcut da tao tren Desktop va Start Menu
echo.
echo ℹ️  File exe da dong goi san Python ^& cac thu vien can thiet.
echo    Lan dau chay se tu dong tai model XTTS-v2 (can internet, ~1.7GB).
echo.
echo Nhan phim bat ky de thoat...
pause >nul


