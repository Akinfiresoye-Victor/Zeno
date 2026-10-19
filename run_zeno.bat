@echo off
title Zeno Desktop AI Assistant
cd /d "%~dp0"

:: Check if virtual environment python exists
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    start "" "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
) else (
    start "" python "%~dp0main.py"
)
exit /b 0
