@echo off
REM Script để test load TTS model, chạy nhiều lần cho đến khi thành công

echo ========================================
echo TEST TTS MODEL LOADER
echo ========================================
echo.

REM Check Python version
py -3.11 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Using Python 3.11...
    py -3.11 test_tts_model.py
) else (
    echo Python 3.11 not found, trying default Python...
    python test_tts_model.py
)

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo TEST PASSED - Model loaded successfully!
    echo ========================================
    pause
) else (
    echo.
    echo ========================================
    echo TEST FAILED - Check error above
    echo ========================================
    echo.
    echo Press any key to run test again...
    pause >nul
    goto :eof
)

