@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=venv"
set "PY_LAUNCHER="

echo.
echo ============================================================
echo   ViciAuto - Install
echo ============================================================
echo.

rem --- Locate a Python 3 interpreter --------------------------------------
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_LAUNCHER=py -3"
    goto :python_found
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_LAUNCHER=python"
    goto :python_found
)

echo [ERROR] Python 3 was not found on PATH.
echo         Install it from https://www.python.org/downloads/ and make
echo         sure "Add python.exe to PATH" is selected during setup.
echo.
pause
exit /b 1

:python_found
echo [OK] Using Python: %PY_LAUNCHER%

rem --- Create the virtual environment -------------------------------------
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [OK] Virtual environment already present at %VENV_DIR%\
) else (
    echo [..] Creating virtual environment at %VENV_DIR%\
    %PY_LAUNCHER% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        echo.
        pause
        exit /b 1
    )
)

rem --- Install dependencies -----------------------------------------------
echo [..] Upgrading pip
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed

echo [..] Installing dependencies from requirements.txt
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [OK] Installation complete.
echo      Start the app with: run.bat
echo.
pause
exit /b 0

:failed
echo.
echo [ERROR] Installation failed. See the messages above.
echo.
pause
exit /b 1
