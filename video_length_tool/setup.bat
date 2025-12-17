@echo off
setlocal enabledelayedexpansion

echo ========================================
echo FFmpeg setup for VideoLengthTool (Windows)
echo ========================================
echo.

REM Directory of this script (video_length_tool folder)
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM URL for prebuilt FFmpeg (64-bit, GPL, latest master build)
set FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip
set FFMPEG_ZIP=ffmpeg_download.zip
set FFMPEG_TMP=ffmpeg_tmp

echo This script will:
echo   1) Download a prebuilt FFmpeg for Windows (64-bit)
echo   2) Extract it
echo   3) Copy ffmpeg.exe next to this folder/tool
echo.
pause

echo.
echo Step 1: Downloading FFmpeg...
if exist "%FFMPEG_ZIP%" del /f /q "%FFMPEG_ZIP%" >nul 2>&1

powershell -Command "try { Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile '%FFMPEG_ZIP%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo Error: Failed to download FFmpeg.
    echo Please check your internet connection or download it manually:
    echo   %FFMPEG_URL%
    echo and place ffmpeg.exe next to this script.
    pause
    exit /b 1
)

echo Download completed: %FFMPEG_ZIP%
echo.

echo Step 2: Extracting FFmpeg archive...
if exist "%FFMPEG_TMP%" rmdir /s /q "%FFMPEG_TMP%" >nul 2>&1
mkdir "%FFMPEG_TMP%"

powershell -Command "Expand-Archive -Path '%FFMPEG_ZIP%' -DestinationPath '%FFMPEG_TMP%' -Force"
if errorlevel 1 (
    echo Error: Failed to extract FFmpeg archive.
    echo You can extract it manually and copy ffmpeg.exe next to this script.
    pause
    exit /b 1
)

echo Extraction completed.
echo.

echo Step 3: Locating ffmpeg.exe...
set FFMPEG_EXE_FOUND=

for /r "%FFMPEG_TMP%" %%F in (ffmpeg.exe) do (
    set FFMPEG_EXE_FOUND=%%F
    goto :found_exe
)

:found_exe
if "%FFMPEG_EXE_FOUND%"=="" (
    echo Error: Could not find ffmpeg.exe in extracted files.
    echo Please open folder "%FFMPEG_TMP%" and check manually.
    pause
    exit /b 1
)

echo Found: %FFMPEG_EXE_FOUND%
echo Copying ffmpeg.exe next to this script...

copy /Y "%FFMPEG_EXE_FOUND%" "%SCRIPT_DIR%\ffmpeg.exe" >nul
if errorlevel 1 (
    echo Error: Failed to copy ffmpeg.exe.
    pause
    exit /b 1
)

echo.
echo Cleaning temporary files...
if exist "%FFMPEG_ZIP%" del /f /q "%FFMPEG_ZIP%" >nul 2>&1
if exist "%FFMPEG_TMP%" rmdir /s /q "%FFMPEG_TMP%" >nul 2>&1

echo.
echo ========================================
echo FFmpeg setup completed successfully!
echo ========================================
echo.
echo ffmpeg.exe has been placed in:
echo   %SCRIPT_DIR%
echo.
echo You can now:
echo   - Run:  py -3.11 video_length_tool.py
echo   - Or build exe via build_video_length_tool.bat
echo and the tool will automatically use this ffmpeg.exe.
echo.
pause

endlocal




