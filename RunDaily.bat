@echo off
cd /d "%~dp0"
title Scholarships Hunter - Daily Sweep
call .venv\Scripts\python.exe src\utils\daily_runner.py %*
