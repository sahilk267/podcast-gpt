@echo off
setlocal
cd /d "%~dp0"
title Podcast GPT - Windows CPU Studio
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] Application startup failed. See the message above.
  pause
  exit /b 1
)
endlocal
