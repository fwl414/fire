@echo off
setlocal EnableExtensions
title Fire AI Mobile Start

set "PROJECT_DIR=%~dp0"
set "MOBILE_DIR=%PROJECT_DIR%mobile_app"

if not exist "%MOBILE_DIR%\pubspec.yaml" (
    echo [ERROR] mobile_app\pubspec.yaml not found.
    pause
    exit /b 1
)

cd /d "%MOBILE_DIR%"
flutter pub get
flutter run

pause
endlocal
