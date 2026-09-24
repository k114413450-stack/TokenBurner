@echo off
rem ===================================================================
rem  TokenBurner 3D Quantum Vision HUD Launcher
rem  Pure ASCII English script -- deliberately avoids non-ASCII output so
rem  it cannot break on a console whose codepage is not UTF-8/GBK.
rem
rem  Usage:  run_hud_3d.bat          -> launch silently (no console)
rem          run_hud_3d.bat debug    -> launch in this console so a crash
rem                                     traceback stays visible
rem ===================================================================

cd /d "%~dp0"

echo ===================================================
echo   TOKENBURNER 3D QUANTUM CORE LAUNCHER v1.0.1
echo ===================================================

set "TB_PY="

rem --- 1) Find a REAL Python 3. -------------------------------------
rem NOTE: `where python` is NOT a valid check on Windows 10/11. The
rem Microsoft Store installs an alias stub at
rem %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe that resolves in
rem PATH and exits 0, but launching it opens the Store instead of
rem running Python. Always probe by actually executing an import.
python -c "import sys" >nul 2>nul
if not errorlevel 1 set "TB_PY=python"

if not defined TB_PY (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "TB_PY=py -3"
)

if not defined TB_PY (
    echo [ERROR] No working Python 3 interpreter found.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

rem --- 2) Verify the hard dependencies before launching. ------------
%TB_PY% -c "import webview, PIL" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Missing Python packages.
    echo         Run this once from the project folder:
    echo             %TB_PY% -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem --- 3) Locate the matching pythonw.exe (no console window). ------
set "TB_RUN=%TB_PY%"
if "%TB_PY%"=="python" (
    for %%I in (python.exe) do set "TB_PYEXE=%%~$PATH:I"
    if defined TB_PYEXE set "TB_PYW=%TB_PYEXE:python.exe=pythonw.exe%"
)

echo Detected interpreter: %TB_PY%

rem --- 4) Stop a previously running instance. -----------------------
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
start "" %TB_RUN% "%~dp0src\hud_3d.py"
goto :done

:debug
rem --- Debug launch: keeps stdout/stderr in this console. -----------
rem Any startup error is usually an unimportant missing package; the
rem traceback above this line is the useful part.
%TB_RUN% "%~dp0src\hud_3d.py"
if errorlevel 1 (
    echo.
    echo [ERROR] TokenBurner exited with the error shown above.
    pause
    exit /b 1
)

:done
echo TokenBurner 3D Quantum Core running in top-right corner.
exit /b 0
