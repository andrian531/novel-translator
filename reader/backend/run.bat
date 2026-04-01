@echo off
cd /d "%~dp0"

set "VENV_ACTIVATE=%~dp0..\..\venv\Scripts\activate.bat"

if exist "%VENV_ACTIVATE%" (
    call "%VENV_ACTIVATE%"
) else (
    echo [!] venv not found. Run install.bat from project root first.
    pause
    exit /b 1
)

pip install -r requirements.txt -q

echo.
echo  Novel Reader API
echo  http://localhost:8000
echo  Press Ctrl+C to stop
echo.

uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
