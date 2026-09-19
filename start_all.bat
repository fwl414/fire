@echo off
setlocal EnableExtensions
title Fire AI Agent V1.0.0 Start All

echo ======================================================
echo   Fire AI Agent V1.0.0 - One Click Start
echo ======================================================
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"

echo [1/5] Checking project folders...

if not exist "%BACKEND_DIR%\main.py" (
    echo [ERROR] backend\main.py not found.
    echo Please run this script from the project root folder.
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] frontend\package.json not found.
    echo Please run this script from the project root folder.
    pause
    exit /b 1
)

echo [2/5] Checking Python virtual environment...
cd /d "%BACKEND_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.14 virtual environment...
    py -3.14 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create Python 3.14 virtual environment.
        echo Please install Python 3.14 and make sure "py -3.14" works.
        pause
        exit /b 1
    )
)

echo [3/5] Installing backend dependencies...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    pause
    exit /b 1
)

echo [4/5] Checking frontend dependencies...
cd /d "%FRONTEND_DIR%"

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call yarn install
    if errorlevel 1 (
        echo [ERROR] Frontend dependency installation failed.
        echo Please install Node.js first, then run: corepack enable
        pause
        exit /b 1
    )
) else (
    echo node_modules found. Skip yarn install.
)

echo [5/5] Starting backend and frontend...
echo.
echo Backend docs: http://127.0.0.1:8000/docs
echo Frontend:     http://127.0.0.1:5173/dashboard
echo.

start "Fire AI Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && call .venv\Scripts\activate.bat && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 4 /nobreak > nul

start "Fire AI Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm run dev"

timeout /t 6 /nobreak > nul

start "" "http://127.0.0.1:5173/dashboard"
start "" "http://127.0.0.1:8000/docs"

echo ======================================================
echo Started.
echo Keep the two opened command windows running.
echo Close them to stop backend and frontend.
echo ======================================================
echo.
pause
endlocal
