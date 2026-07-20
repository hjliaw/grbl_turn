@echo off
rem grbl_turn installer for Windows 10.
rem
rem Prereq: Python 3.10+ from python.org (check "Add python.exe to PATH"
rem during its setup, which also installs the "py" launcher).
rem
rem Run from the repo folder (double-click works):
rem     install-win.bat              install + Desktop shortcut; on an
rem                                  existing working install, update
rem                                  the app code only
rem     install-win.bat /autostart   also start the app at login
rem     install-win.bat /fresh       wipe the venv, full reinstall
rem
rem Installs into %LOCALAPPDATA%\grbl_turn\venv and creates a shortcut
rem that runs the app with no console window (pythonw).

setlocal
set "REPO=%~dp0"
set "VENVDIR=%LOCALAPPDATA%\grbl_turn\venv"
set "PYEXE=%VENVDIR%\Scripts\python.exe"
set "PYW=%VENVDIR%\Scripts\pythonw.exe"
set "ICO=%VENVDIR%\Lib\site-packages\grbl_turn\resources\icons\grbl_turn.ico"

set "FRESH=0"
set "AUTOSTART=0"
for %%A in (%*) do (
    if /i "%%A"=="/fresh" set "FRESH=1"
    if /i "%%A"=="/autostart" set "AUTOSTART=1"
)
if "%FRESH%"=="1" if exist "%VENVDIR%" rmdir /s /q "%VENVDIR%"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher not found. Install Python 3 from python.org
    echo and rerun this script.
    goto :fail
)

rem With a working venv only the app package needs replacing -- skip
rem venv creation and dependency resolution; PySide6 stays as-is.
set "UPDATE=0"
if not exist "%PYEXE%" goto :detected
"%PYEXE%" -c "import grbl_turn" >nul 2>nul
if not errorlevel 1 set "UPDATE=1"
:detected

rem A stale build\ from an earlier install can shadow newer source files
rem (setuptools stages the wheel there and only replaces "older" files).
if exist "%REPO%build" rmdir /s /q "%REPO%build"

if "%UPDATE%"=="0" goto :fullinstall
echo ==^> Existing install found: updating app code only. Use /fresh
echo     for a full reinstall.
"%PYEXE%" -m pip install --no-deps "%REPO%."
if errorlevel 1 goto :fail
goto :installed

:fullinstall
echo ==^> Creating virtualenv at %VENVDIR%
py -3 -m venv "%VENVDIR%"
if errorlevel 1 goto :fail

echo ==^> Installing grbl_turn (pulls PySide6 + pyserial)
"%PYEXE%" -m pip install --upgrade pip wheel
"%PYEXE%" -m pip install "%REPO%."
if errorlevel 1 goto :fail

:installed
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

if "%AUTOSTART%"=="1" (
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
