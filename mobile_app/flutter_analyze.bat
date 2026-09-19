@echo off
REM Why this wrapper exists:
REM   `flutter analyze` passes the project root to the analysis server over LSP.
REM   When that path contains non-ASCII characters (this repo folder is named
REM   "fire_ai_agent_v1 - <CJK chars>"), the message framing no longer matches and
REM   the analysis server dies with:
REM     FormatException: Unexpected end of input ... LspByteStreamServerChannel._readMessage
REM   The very same code analyzed through a pure-ASCII path works fine, so this
REM   script points an ASCII directory junction (mklink /J, no admin rights needed)
REM   at this folder and runs `flutter analyze` there. Sources are not copied.
REM
REM Usage, from the mobile_app directory:
REM   flutter_analyze.bat
REM   flutter_analyze.bat --fatal-infos=false
REM To put the junction elsewhere:  set FLUTTER_ASCII_LINK=D:\mob_ascii
setlocal
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

if not defined FLUTTER_ASCII_LINK set "FLUTTER_ASCII_LINK=F:\mob_ascii"

if not exist "%FLUTTER_ASCII_LINK%\pubspec.yaml" (
  if exist "%FLUTTER_ASCII_LINK%" rmdir "%FLUTTER_ASCII_LINK%" 2>nul
  mklink /J "%FLUTTER_ASCII_LINK%" "%APP_DIR%" >nul
  if errorlevel 1 goto link_failed
)

cd /d "%FLUTTER_ASCII_LINK%"
flutter analyze %*
set "RC=%ERRORLEVEL%"
exit /b %RC%

:link_failed
echo [ERROR] Could not create the ASCII junction.
echo   mklink /J "%FLUTTER_ASCII_LINK%" "%APP_DIR%"
echo If that drive is not writable, set FLUTTER_ASCII_LINK to another ASCII folder first.
exit /b 1
