@echo off
REM RepoMedic setup: install backend and frontend dependencies.
REM Run once before start.bat. Open a Windows Terminal and run: setup.bat

cd /d "%~dp0"

echo [RepoMedic] ========================================
echo [RepoMedic]  RepoMedic setup
echo [RepoMedic] ========================================

echo [RepoMedic] Creating backend virtual environment at backend\.venv
python -m venv backend\.venv
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: could not create venv. Is Python 3.10+ installed and on PATH?
    exit /b 1
)

call backend\.venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: could not activate venv.
    exit /b 1
)

echo [RepoMedic] Installing backend dependencies (fastapi, uvicorn, pydantic, httpx, pytest, ruff)
pip install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: backend dependency install failed. Check your internet connection and try again.
    exit /b 1
)

echo [RepoMedic] Installing frontend dependencies (npm install in frontend/)
cd frontend
npm install
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: frontend dependency install failed. Check your internet connection and try again.
    cd ..
    exit /b 1
)
cd ..

echo [RepoMedic] ========================================
echo [RepoMedic] Setup complete. Run start.bat to launch RepoMedic.
echo [RepoMedic] ========================================
