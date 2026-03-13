@echo off
title Novel Translator CLI
cls
python main.py
if errorlevel 1 (
    echo.
    echo [!] An error occurred while running the application.
    echo [!] Make sure Python is installed and requirements are met.
    pause
)
