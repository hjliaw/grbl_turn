@echo off
rem grbl_turn uninstaller for Windows 10. Removes everything
rem install-win.bat created: the venv, the Desktop shortcut, and the
rem Startup shortcut (if /autostart was used).
rem
rem Run from anywhere (double-click works):
rem     uninstall-win.bat            uninstall, keep saved settings
rem     uninstall-win.bat /purge     also delete saved op parameters
rem                                  (registry key HKCU\Software\grbl_turn)

setlocal
set "APPDIR=%LOCALAPPDATA%\grbl_turn"

echo ==^> Removing shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Remove-Item ([Environment]::GetFolderPath('Desktop') + '\grbl_turn.lnk') -ErrorAction SilentlyContinue;" ^
  "Remove-Item ([Environment]::GetFolderPath('Startup') + '\grbl_turn.lnk') -ErrorAction SilentlyContinue"

if exist "%APPDIR%" (
    echo ==^> Removing %APPDIR%
    rmdir /s /q "%APPDIR%"
)
if exist "%APPDIR%" (
    echo Could not remove %APPDIR% — is the app still running?
    echo Close it and rerun this script.
    goto :fail
)

if /i "%~1"=="/purge" (
    echo ==^> Removing saved settings
    reg delete HKCU\Software\grbl_turn /f >nul 2>nul
)

echo.
echo Done. grbl_turn is uninstalled.
if /i not "%~1"=="/purge" echo (Saved op parameters kept; rerun with /purge to remove them.)
pause
exit /b 0

:fail
pause
exit /b 1
