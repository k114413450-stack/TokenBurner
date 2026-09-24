@echo off
rem TokenBurner 3D Quantum Vision HUD Launcher
rem Pure ASCII English script

cd /d "%~dp0"

echo ===================================================
echo   TOKENBURNER 3D QUANTUM CORE LAUNCHER v1.0.0
echo ===================================================

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Starting TokenBurner 3D Vision Core...
taskkill /F /FI "WINDOWTITLE eq TokenBurner 3D Hologram" >nul 2>nul
start "" python "%~dp0src\hud_3d.py"

echo TokenBurner 3D Quantum Core running in top-right corner.
exit /b 0
