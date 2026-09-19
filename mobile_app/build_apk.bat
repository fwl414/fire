@echo off
REM Why this wrapper exists:
REM   `flutter build apk` needs JAVA_HOME / ANDROID_HOME on PATH, and the flutter
REM   tool chain mis-handles non-ASCII project paths (this repo folder is named
REM   "fire_ai_agent_v1 - <CJK chars>"). This script points an ASCII directory
REM   junction (mklink /J, no admin rights needed) at this folder and builds there.
REM   Sources are not copied.
REM
REM Usage, from the mobile_app directory:
REM   build_apk.bat                                   ^<-- emulator default
REM   build_apk.bat http://192.168.1.10:8000          ^<-- LAN server
REM   build_apk.bat https://fire.example.com          ^<-- HTTPS deployment
REM
REM The API base URL is compiled into the APK via --dart-define, so it must be
REM passed at build time. Overridable locations:
REM   set FLUTTER_BIN=F:\flutter\bin
REM   set JDK_DIR=F:\jdk\jdk17
REM   set ANDROID_SDK_DIR=F:\android-sdk
REM   set FLUTTER_ASCII_LINK=F:\mob_ascii
setlocal
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

if not defined FLUTTER_ASCII_LINK set "FLUTTER_ASCII_LINK=F:\mob_ascii"
if not defined FLUTTER_BIN set "FLUTTER_BIN=F:\flutter\bin"
if not defined JDK_DIR set "JDK_DIR=F:\jdk\jdk17"
if not defined ANDROID_SDK_DIR set "ANDROID_SDK_DIR=F:\android-sdk"

set "API_BASE_URL=%~1"
if "%API_BASE_URL%"=="" set "API_BASE_URL=http://10.0.2.2:8000"

if not exist "%FLUTTER_BIN%\flutter.bat" (
  echo [ERROR] flutter.bat not found. Set FLUTTER_BIN and retry.
  exit /b 1
)
if not exist "%JDK_DIR%\bin\java.exe" (
  echo [ERROR] JDK not found at "%JDK_DIR%". Set JDK_DIR and retry.
  exit /b 1
)
if not exist "%ANDROID_SDK_DIR%\platform-tools" (
  echo [ERROR] Android SDK not found at "%ANDROID_SDK_DIR%". Set ANDROID_SDK_DIR and retry.
  exit /b 1
)

if not exist "%FLUTTER_ASCII_LINK%\pubspec.yaml" (
  if exist "%FLUTTER_ASCII_LINK%" rmdir "%FLUTTER_ASCII_LINK%" 2>nul
  mklink /J "%FLUTTER_ASCII_LINK%" "%APP_DIR%" >nul
  if errorlevel 1 goto link_failed
)

set "JAVA_HOME=%JDK_DIR%"
set "ANDROID_HOME=%ANDROID_SDK_DIR%"
set "ANDROID_SDK_ROOT=%ANDROID_SDK_DIR%"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\cmdline-tools\latest\bin;%ANDROID_HOME%\platform-tools;%FLUTTER_BIN%;%PATH%"

echo [INFO] project    : %FLUTTER_ASCII_LINK%
echo [INFO] API_BASE_URL: %API_BASE_URL%
echo [INFO] JAVA_HOME  : %JAVA_HOME%
echo [INFO] ANDROID_HOME: %ANDROID_HOME%
echo.

cd /d "%FLUTTER_ASCII_LINK%"

call "%FLUTTER_BIN%\flutter.bat" pub get
if errorlevel 1 goto build_failed

call "%FLUTTER_BIN%\flutter.bat" build apk --release --dart-define=API_BASE_URL=%API_BASE_URL%
if errorlevel 1 goto build_failed

echo.
echo [OK] Release APK:
for %%F in ("%FLUTTER_ASCII_LINK%\build\app\outputs\flutter-apk\*.apk") do echo   %%~fF  (%%~zF bytes)
exit /b 0

:link_failed
echo [ERROR] Could not create the ASCII junction.
echo   mklink /J "%FLUTTER_ASCII_LINK%" "%APP_DIR%"
exit /b 1

:build_failed
echo.
echo [ERROR] Build failed. Run flutter_analyze.bat and check the Gradle output above.
exit /b 1
