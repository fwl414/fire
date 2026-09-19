@echo off
setlocal EnableExtensions
title Stop Fire AI Agent

echo Stopping processes on ports 8000 and 5173...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000"') do (
    taskkill /PID %%a /F > nul 2> nul
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173"') do (
    taskkill /PID %%a /F > nul 2> nul
)

echo Done.
pause
endlocal
