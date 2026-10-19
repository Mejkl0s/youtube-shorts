@echo off
setlocal
cd /d "%~dp0"
if not exist "scripts\windows.ps1" (
  echo Nejprve kliknete na ZIP pravym tlacitkem a zvolte Extrahovat vse.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -CheckOnly
pause
