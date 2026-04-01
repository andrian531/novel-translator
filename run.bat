@echo off
title Novel Translator CLI
cls

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_ACTIVATE=%SCRIPT_DIR%\venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
    echo [!] venv not found. Run install.bat first.
    pause
    exit /b 1
)

call "%VENV_ACTIVATE%"
python main.py
if errorlevel 1 (
    echo.
    echo [!] An error occurred while running the application.
    echo [!] Make sure install.bat has been run successfully.
    pause
)
