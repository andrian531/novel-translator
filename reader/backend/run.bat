@echo off
cd /d "%~dp0"

pip install -r requirements.txt -q

echo.
echo  Novel Reader API
echo  http://localhost:8000
echo  Press Ctrl+C to stop
echo.

uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
