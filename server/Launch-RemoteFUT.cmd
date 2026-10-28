@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-RemoteFUT.ps1" %*
pause
