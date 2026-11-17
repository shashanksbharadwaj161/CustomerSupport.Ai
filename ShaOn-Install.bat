@echo off
rem ShaOn Voice AI - install everything and print a public link (docs\SHARE.md).
rem Runs scripts\install.ps1 with -ExecutionPolicy Bypass for this run only: no system policy is changed.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
echo.
pause
