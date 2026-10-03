@echo off
title SkyFlight
cd /d "%~dp0"

set "PY=%~dp0runtime\python.exe"

if not exist "%PY%" (
    echo.
    echo  ERROR: bundled Python not found:
    echo    %PY%
    echo  Make sure the "runtime" folder sits next to this file.
    echo.
    pause
    exit /b 1
)

echo.
echo   ==========================================
echo      SkyFlight - Flight Simulator  v1.1.0
echo   ==========================================
echo.
echo   CONTROLS
echo   ------------------------------------------
echo    Pitch       S = nose UP     W = nose DOWN
echo                (Down / Up arrows also work)
echo    Roll        D = right       A = left
echo    Yaw         E = right       Q = left
echo    Throttle    Shift = more    Ctrl = less
echo    Full / Cut  Z = full        X = idle
echo    Flaps       F
echo    Brakes      B
echo    Camera      C
echo    Mouse fly   M
echo    Pause       P
echo    Restart     R
echo    FULLSCREEN  F11   (or Alt+Enter)
echo    Help        H
echo    Quit        Esc
echo   ------------------------------------------
echo    TAKE OFF: press Z, wait for ~100 km/h,
echo              then HOLD S to lift the nose.
echo   ------------------------------------------
echo.

"%PY%" -m skyflight

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo   [EXITED WITH ERROR %RC%]
    echo   Please send a screenshot of the messages above.
) else (
    echo   Flight session ended normally.
)
echo.
pause
