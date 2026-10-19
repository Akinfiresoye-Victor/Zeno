@echo off
title Zeno Desktop AI Assistant (Debug Console)
cd /d "%~dp0"
echo ========================================================
echo   Starting Zeno Desktop AI Assistant in Debug Mode
echo ========================================================
echo.

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
) else (
    python "%~dp0main.py"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application closed with error code %ERRORLEVEL%.
    pause
)
