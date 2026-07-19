@echo off
rem grbl_turn installer for Windows 10.
rem
rem Prereq: Python 3.10+ from python.org (check "Add python.exe to PATH"
rem during its setup, which also installs the "py" launcher).
rem
rem Run from the repo folder (double-click works):
rem     install-win.bat              install + Desktop shortcut
rem     install-win.bat /autostart   also start the app at login
rem
rem Installs into %LOCALAPPDATA%\grbl_turn\venv and creates a shortcut
rem that runs the app with no console window (pythonw).

setlocal
set "REPO=%~dp0"
set "VENVDIR=%LOCALAPPDATA%\grbl_turn\venv"
set "PYW=%VENVDIR%\Scripts\pythonw.exe"
set "ICO=%VENVDIR%\Lib\site-packages\grbl_turn\resources\icons\grbl_turn.ico"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher not found. Install Python 3 from python.org
    echo and rerun this script.
    goto :fail
)

echo ==^> Creating virtualenv at %VENVDIR%
py -3 -m venv "%VENVDIR%"
if errorlevel 1 goto :fail

rem A stale build\ from an earlier install can shadow newer source files
rem (setuptools stages the wheel there and only replaces "older" files).
if exist "%REPO%build" rmdir /s /q "%REPO%build"

echo ==^> Installing grbl_turn (pulls PySide6 + pyserial)
"%VENVDIR%\Scripts\python.exe" -m pip install --upgrade pip wheel
"%VENVDIR%\Scripts\python.exe" -m pip install "%REPO%."
if errorlevel 1 goto :fail

echo ==^> Smoke test (imports only)
"%VENVDIR%\Scripts\python.exe" -c "from PySide6.QtSvgWidgets import QSvgWidget; import serial; import grbl_turn.app; print('imports OK')"
if errorlevel 1 goto :fail

echo ==^> Desktop shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\grbl_turn.lnk');" ^
  "$s.TargetPath = '%PYW%';" ^
  "$s.Arguments = '-m grbl_turn';" ^
  "$s.WorkingDirectory = [Environment]::GetFolderPath('UserProfile');" ^
  "$s.IconLocation = '%ICO%';" ^
  "$s.Description = 'Conversational lathe GUI';" ^
  "$s.Save()"
if errorlevel 1 goto :fail

if /i "%~1"=="/autostart" (
    echo ==^> Autostart at login
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ws = New-Object -ComObject WScript.Shell;" ^
      "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\grbl_turn.lnk');" ^
      "$s.TargetPath = '%PYW%';" ^
      "$s.Arguments = '-m grbl_turn';" ^
      "$s.WorkingDirectory = [Environment]::GetFolderPath('UserProfile');" ^
      "$s.IconLocation = '%ICO%';" ^
      "$s.Save()"
    if errorlevel 1 goto :fail
)

echo.
echo Done. Launch from the Desktop shortcut, or:
echo     "%PYW%" -m grbl_turn
echo GRBL appears as a COM port (check Device Manager if unsure).
pause
exit /b 0

:fail
echo.
echo Install FAILED — see the messages above.
pause
exit /b 1
