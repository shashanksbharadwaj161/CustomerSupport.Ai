@echo off
rem ShaOn Voice AI - share by public link ($0). Double-click me. Keep the window open while sharing.
title ShaOn Voice AI - share link
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\share.ps1" %*
echo.
pause
