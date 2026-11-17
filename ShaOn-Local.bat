@echo off
rem ShaOn Voice AI - LOCAL PREVIEW: full app on this PC only, no passcode, key/model editable in Settings.
rem For a public link use ShaOn-Share.bat instead (passcodes, key editing locked).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local.ps1" %*
echo.
pause
