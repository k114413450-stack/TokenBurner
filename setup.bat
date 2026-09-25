@echo off
rem ===================================================================
rem  TokenBurner dependency installer / repair
rem  Double-click this after cloning, or whenever the launcher says a
rem  package is missing. Pure ASCII on purpose (see run_hud_3d.bat).
rem
rem  What it does: creates .venv\ next to this file, then pip-installs
rem  requirements.txt into it. Nothing outside this folder is touched.
rem  Safe to run twice - it reuses an existing working .venv.
rem ===================================================================

setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"

echo ===================================================
echo   TOKENBURNER SETUP - install dependencies
echo ===================================================
echo.
echo This downloads pywebview, Pillow, psutil, numpy,
echo opencv-python and pyautogui into .venv\ - roughly 70 MB.
echo It can take a few minutes on a slow connection.
echo.

if not exist "requirements.txt" (
    echo [ERROR] requirements.txt was not found next to this script.
    echo         This file only works from inside the project folder.
    echo.
    pause
    exit /b 1
)

rem --- 1) Find a real Python 3 to build the virtualenv from. --------
set "TB_BOOT="
python -c "import sys" >nul 2>nul
if not errorlevel 1 set "TB_BOOT=python"
if not defined TB_BOOT (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "TB_BOOT=py -3"
)
if not defined TB_BOOT (
    echo [ERROR] No working Python 3 interpreter was found.
    echo         Install Python 3.10 or newer from python.org, tick
    echo         "Add python.exe to PATH" during setup, then run me again.
    echo.
    pause
    exit /b 1
)
echo Step 1/4  Using interpreter: %TB_BOOT%

set "TB_VENV_PY=%~dp0.venv\Scripts\python.exe"

rem --- 2) Create the virtualenv if missing or broken. --------------
if exist "%TB_VENV_PY%" (
    "%TB_VENV_PY%" -c "import sys" >nul 2>nul
    if errorlevel 1 (
        echo Step 2/4  Existing .venv is unusable - rebuilding it.
        rmdir /s /q "%~dp0.venv"
    )
)
if not exist "%TB_VENV_PY%" (
    echo Step 2/4  Creating virtualenv in .venv ...
    %TB_BOOT% -m venv ".venv"
    if errorlevel 1 goto :venvfail
)
if not exist "%TB_VENV_PY%" goto :venvfail
echo Step 2/4  Virtualenv ready.

rem --- 3) Install dependencies. -------------------------------------
echo Step 3/4  Upgrading pip ...
"%TB_VENV_PY%" -m pip install --upgrade pip

echo Step 3/4  Installing packages - please wait ...
"%TB_VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    rem Retry once with certificate verification relaxed: a stale
    rem corporate/AV HTTPS proxy is the usual cause on locked-down
    rem machines, and it looks identical to "no internet".
    echo.
    echo First attempt failed. Retrying with relaxed TLS checking ...
    "%TB_VENV_PY%" -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
)
if errorlevel 1 goto :pipfail

rem --- 4) Verify. ---------------------------------------------------
echo.
echo Step 4/4  Verifying imports ...
"%TB_VENV_PY%" -c "import webview, PIL, psutil" >nul 2>nul
if errorlevel 1 goto :verifyfail
echo   OK   pywebview / Pillow / psutil  - required to start the HUD

"%TB_VENV_PY%" -c "import numpy, cv2, pyautogui" >nul 2>nul
if errorlevel 1 (
    echo   WARN numpy / opencv / pyautogui missing.
    echo        The HUD still runs; the optional YOLO auto-approver
    echo        will report itself as unavailable.
) else (
    echo   OK   numpy / opencv / pyautogui  - YOLO auto-approver enabled
)

echo.
echo ===================================================
echo   DONE - close this window and double-click
echo   run_hud_3d.bat to start the HUD.
echo ===================================================
echo.
pause
exit /b 0

:venvfail
echo.
echo [ERROR] Could not create the virtualenv in .venv
echo        Check that you have write access to this folder and that
echo        this path has no unusual characters, then run me again.
echo.
pause
exit /b 1

:pipfail
echo.
echo [ERROR] pip could not install the packages.
echo        Most common cause: no internet, or a blocked PyPI mirror.
echo        Try again on a normal connection, or set a mirror:
echo            .venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
pause
exit /b 1

:verifyfail
echo.
echo [ERROR] Packages installed but pywebview still cannot be imported.
echo        Scroll up for the traceback. On some machines pywebview
echo        needs the Microsoft Edge WebView2 Runtime, which ships with
echo        Windows 11 and current Windows 10 updates.
echo.
pause
exit /b 1
