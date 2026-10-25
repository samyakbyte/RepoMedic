@echo off
setlocal
REM RepoMedic setup: install backend Python venv + frontend npm dependencies.
REM Run once before start.bat.

cd /d "%~dp0"

echo [RepoMedic] ========================================
echo [RepoMedic]  RepoMedic Setup
echo [RepoMedic] ========================================

if not exist ".env" (
    if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
        echo [RepoMedic] Created .env from .env.example
    )
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: Python 3.10+ not found on PATH.
    echo [RepoMedic] Install Python from https://www.python.org/downloads/ and check "Add Python to PATH".
    pause
    exit /b 1
)

echo [RepoMedic] Creating backend virtual environment at backend\.venv ...
python -m venv backend\.venv
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: Could not create virtual environment at backend\.venv
    pause
    exit /b 1
)

echo [RepoMedic] Installing backend Python dependencies ...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: Backend dependency install failed. Check your internet connection.
    pause
    exit /b 1
)

where npm.cmd >nul 2>nul
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: Node.js / npm not found on PATH.
    echo [RepoMedic] Install Node.js LTS from https://nodejs.org/ and re-run setup.bat.
    pause
    exit /b 1
)

echo [RepoMedic] Installing frontend dependencies (npm install in frontend\) ...
pushd frontend
call npm.cmd install
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: Frontend npm install failed. Check your internet connection.
    popd
    pause
    exit /b 1
)
popd

echo.
echo [RepoMedic] ========================================
echo [RepoMedic] Setup complete!
echo [RepoMedic] Optional (for AI repair): ollama pull qwen2.5-coder:1.5b
echo [RepoMedic] Next step: double-click or run start.bat
echo [RepoMedic] ========================================
pause
