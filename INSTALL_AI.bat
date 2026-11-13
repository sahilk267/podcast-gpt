@echo off
setlocal
cd /d "%~dp0"
title Optional SadTalker CPU Installation
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_sadtalker.ps1"
if errorlevel 1 (
 echo [ERROR] SadTalker installation was not completed.
 pause
 exit /b 1
)
echo SadTalker setup finished. Restart START.bat.
pause
endlocal
