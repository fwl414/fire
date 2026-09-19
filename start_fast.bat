@echo off
setlocal EnableExtensions
title Fire AI Agent V1.0.0 Fast Start

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"

if not exist "%BACKEND_DIR%\main.py" (
    echo [ERROR] backend\main.py not found.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] frontend\package.json not found.
    pause
    exit /b 1
)

start "Fire AI Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak > nul

start "Fire AI Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

timeout /t 6 /nobreak > nul

start "" "http://127.0.0.1:5173/dashboard"
start "" "http://127.0.0.1:8000/docs"

endlocal
