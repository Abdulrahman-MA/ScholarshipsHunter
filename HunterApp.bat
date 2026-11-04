@echo off
cd /d "%~dp0"
TITLE Scholarships Hunter - Desktop App
if exist ".venv\Scripts\python.exe" (
    call ".venv\Scripts\python.exe" -m src.desktop %*
) else (
    python -m src.desktop %*
)
if errorlevel 1 pause
