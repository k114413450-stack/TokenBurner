@echo off
rem ===================================================================
rem  TokenBurner 3D Quantum Vision HUD Launcher
rem  Pure ASCII English script -- deliberately avoids non-ASCII output so
rem  it cannot break on a console whose codepage is not UTF-8/GBK.
rem
rem  Usage:  run_hud_3d.bat          launch silently (no console window)
rem          run_hud_3d.bat debug    launch in this console so a crash
rem                                     traceback stays visible
rem ===================================================================

setlocal EnableExtensions
cd /d "%~dp0"

echo ===================================================
echo   TOKENBURNER 3D QUANTUM CORE LAUNCHER v1.0.2
echo ===================================================

set "TB_VENV_PY=%~dp0.venv\Scripts\python.exe"
set "TB_VENV_PYW=%~dp0.venv\Scripts\pythonw.exe"

rem --- Interpreter discovery -----------------------------------------
rem Order: the project virtualenv first, then any Python 3 that already
rem has pywebview. NOTE: `where python` is NOT a valid check on Windows
rem 10/11 - the Microsoft Store ships an alias stub at
rem %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe that resolves in
rem PATH but opens the Store instead of running Python. Always probe by
rem actually executing an import and reading the exit code.
:detect
set "TB_PY="

if exist "%TB_VENV_PY%" (
    "%TB_VENV_PY%" -c "import webview" >nul 2>nul
    if not errorlevel 1 set "TB_PY=%TB_VENV_PY%"
)

if not defined TB_PY (
    python -c "import webview" >nul 2>nul
    if not errorlevel 1 set "TB_PY=python"
)

if not defined TB_PY (
    py -3 -c "import webview" >nul 2>nul
    if not errorlevel 1 set "TB_PY=py -3"
)

if not defined TB_PY goto :need_setup
goto :launch

:need_setup
rem --- Nothing usable. Name the missing package, offer the repair. ---
echo.
echo [ERROR] pywebview is not installed for any Python on this machine,
echo         so the HUD cannot start. Nothing is broken - the
echo         dependencies simply have not been installed yet.
echo.

set "TB_BOOT="
python -c "import sys" >nul 2>nul
if not errorlevel 1 set "TB_BOOT=python"
if not defined TB_BOOT (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "TB_BOOT=py -3"
)

if not defined TB_BOOT (
    echo [ERROR] No working Python 3 interpreter was found either.
    echo         Install Python 3.10 or newer from python.org and tick
    echo         "Add python.exe to PATH" during setup, then run me again.
    pause
    exit /b 1
)

echo Python found: %TB_BOOT%
echo.
set /p "TB_ANS=Install the dependencies now? [Y/n]: "
if /i "%TB_ANS%"=="n" goto :manual

call "%~dp0setup.bat"
echo.
echo Re-checking for pywebview...
if not exist "%TB_VENV_PY%" goto :failed
goto :detect

:manual
echo.
echo To install by hand, run these two lines in this folder:
echo     python -m venv .venv
echo     .venv\Scripts\python -m pip install -r requirements.txt
echo.
pause
exit /b 1

:failed
echo.
echo [ERROR] Setup finished but .venv\Scripts\python.exe still cannot
echo         import pywebview. Scroll up for the pip error message.
pause
exit /b 1

:launch
rem --- Locate the matching pythonw.exe (no console window). ---------
set "TB_PYW="
if /i "%TB_PY%"=="%TB_VENV_PY%" set "TB_PYW=%TB_VENV_PYW%"

if not "%TB_PY%"=="python" goto :after_pyw
for %%I in (python.exe) do set "TB_PYEXE=%%~$PATH:I"
if defined TB_PYEXE set "TB_PYW=%TB_PYEXE:python.exe=pythonw.exe%"
:after_pyw

echo Detected interpreter: %TB_PY%

rem --- Stop a previously running instance. --------------------------
rem WARNING: this matches on window title. A frameless window usually
rem still reports its title, but if duplicate HUDs ever appear, close
rem them from the taskbar or use Task Manager.
taskkill /F /FI "WINDOWTITLE eq TokenBurner 3D Hologram" >nul 2>nul

echo Starting TokenBurner 3D Vision Core...

if /i "%~1"=="debug" goto :debug

rem --- Normal launch: silent, no console window. ---------------------
if defined TB_PYW if exist "%TB_PYW%" (
    start "" "%TB_PYW%" "%~dp0src\hud_3d.py"
    goto :done
)
start "" %TB_PY% "%~dp0src\hud_3d.py"
goto :done

:debug
rem --- Debug launch: keeps stdout/stderr in this console. -----------
rem Any startup error is usually an unimportant missing package; the
rem traceback above this line is the useful part.
%TB_PY% "%~dp0src\hud_3d.py"
if errorlevel 1 (
    echo.
    echo [ERROR] TokenBurner exited with the error shown above.
    pause
    exit /b 1
)

:done
echo.
echo TokenBurner 3D Quantum Core is running in the top-right corner.
echo (It has no taskbar entry by design - close it from Task Manager,
echo  or re-run this launcher to restart it.)
exit /b 0
