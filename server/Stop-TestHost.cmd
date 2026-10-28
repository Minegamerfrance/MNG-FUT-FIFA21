@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-TestHost.ps1" -Stop
pause
