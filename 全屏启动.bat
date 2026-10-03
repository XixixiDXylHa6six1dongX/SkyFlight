@echo off
title SkyFlight (Fullscreen)
cd /d "%~dp0"

set "PY=%~dp0runtime\python.exe"

if not exist "%PY%" (
    echo.
    echo  ERROR: bundled Python not found:
    echo    %PY%
    echo.
    pause
    exit /b 1
)

echo.
echo   Starting SkyFlight in FULLSCREEN...
echo.
echo   Press F11 (or Alt+Enter) to switch back to a window.
echo   Press Esc to quit.
echo.

"%PY%" -m skyflight --fullscreen

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
