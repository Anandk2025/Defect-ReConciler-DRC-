@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ============================================
echo  Defect ReConciler (DRC) - local setup
echo  ZDR ^<^> Rally Sync
echo ============================================
echo.

if not exist "%~dp0requirements.txt" (
    echo [ERROR] requirements.txt not found.
    echo Run this file from inside the ZDR Rally Sync Up project folder.
    goto :fail
)

echo [1/4] Looking for Python 3.9 or newer...
set "PY_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)

if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo [ERROR] Python 3.9 or newer was not found on PATH.
    echo.
    echo Install Python from https://www.python.org/downloads/
    echo During setup, enable "Add python.exe to PATH".
    echo Then run this file again.
    goto :fail
)

%PY_CMD% --version
echo.

echo [2/4] Creating virtual environment in .venv ...
if exist "%~dp0.venv\Scripts\python.exe" (
    echo        .venv already exists - reusing it.
) else (
    %PY_CMD% -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv
        goto :fail
    )
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [ERROR] .venv exists but python.exe was not found inside it.
    goto :fail
)

echo.
echo [3/4] Installing libraries from requirements.txt ...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 echo [WARN] Could not upgrade pip. Continuing with the current version.
"%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :pip_fail

echo.
echo [4/4] Environment file...
if exist "%~dp0.env" (
    echo        .env already exists - leaving it unchanged.
) else (
    copy /Y "%~dp0.env.example" "%~dp0.env" >nul
    if errorlevel 1 (
        echo [ERROR] Could not create .env from .env.example
        goto :fail
    )
    echo        Created .env from .env.example.
    echo        Fill in Rally cookies and your Jira API token before running.
)

echo.
echo ============================================
echo  Setup complete.
echo ============================================
echo.
echo Next steps:
echo   1. Open .env and fill in:
echo        RALLY_ZSESSIONID, RALLY_JSESSIONID
echo        ZDR_JIRA_EMAIL, ZDR_JIRA_API_TOKEN
echo   2. Start the dashboard:
echo        .venv\Scripts\python.exe -m src.server
echo      Then open http://127.0.0.1:5050
echo.
echo Optional: Comments Sync Status needs the Claude CLI
echo installed and logged in ^(claude /login^).
echo.
pause
exit /b 0

:pip_fail
echo [ERROR] pip could not install one or more packages.
echo Check your network / proxy and run this file again.
goto :fail

:fail
echo.
echo Setup did not finish. Fix the error above and run this file again.
pause
exit /b 1
