@echo off
chcp 65001 >nul
title GitHub Connectivity Check - SkyFlight

cd /d "%~dp0"

echo ============================================================
echo   GitHub connectivity check
echo ============================================================
echo.

set "PY=%~dp0runtime\python.exe"
if not exist "%PY%" (
    echo  ERROR: bundled Python not found: %PY%
    pause
    exit /b 1
)

"%PY%" tools\github_status.py

echo.
echo ============================================================
pause
