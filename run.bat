@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=venv"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at %VENV_DIR%\
    echo         Run install.bat first to set it up.
    echo.
    pause
    exit /b 1
)

"%VENV_DIR%\Scripts\python.exe" viciauto.py %*
set "EXIT_CODE=%errorlevel%"

rem Exit code 130 is a graceful Ctrl+C shutdown - not an error.
if "%EXIT_CODE%"=="130" exit /b 0

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] ViciAuto exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
