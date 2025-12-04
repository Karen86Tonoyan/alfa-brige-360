@echo off
REM ═══════════════════════════════════════════════════════════════
REM  ALFA_CORE v2.0 - Quick Start
REM ═══════════════════════════════════════════════════════════════

if not exist "venv" (
    echo [!] Run install.bat first!
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo.
echo  Starting ALFA_CORE...
echo  Press Ctrl+C to stop
echo.
python -m alfa_core %*
