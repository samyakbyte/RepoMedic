@echo off
setlocal
REM RepoMedic launch script: starts Ollama (if installed), backend (:8000),
REM frontend (:5173), waits until ready, and opens http://localhost:5173.

cd /d "%~dp0"

echo [RepoMedic] ========================================
echo [RepoMedic]  Starting RepoMedic
echo [RepoMedic] ========================================

if not exist "backend\.venv\Scripts\python.exe" (
    echo [RepoMedic] ERROR: backend\.venv not found. Please run setup.bat first!
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [RepoMedic] ERROR: frontend\node_modules not found. Please run setup.bat first!
    pause
    exit /b 1
)

REM --- 1. Check / Start Ollama safely (never pop up Windows error dialogs) ---
echo [RepoMedic] Checking Ollama...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo [RepoMedic] Ollama is already running on port 11434.
) else (
    where ollama >nul 2>nul
    if %errorlevel% equ 0 (
        echo [RepoMedic] Starting Ollama service from PATH...
        start "" /B ollama serve >nul 2>&1
    ) else if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        echo [RepoMedic] Starting Ollama from %%LOCALAPPDATA%%\Programs\Ollama...
        start "" /B "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve >nul 2>&1
    ) else if exist "%ProgramFiles%\Ollama\ollama.exe" (
        echo [RepoMedic] Starting Ollama from %%ProgramFiles%%\Ollama...
        start "" /B "%ProgramFiles%\Ollama\ollama.exe" serve >nul 2>&1
    ) else (
        echo [RepoMedic] NOTE: Ollama is not installed or not running yet.
        echo [RepoMedic]       Diagnostics still work! For AI patching, install https://ollama.com
        echo [RepoMedic]       and run: ollama pull qwen2.5-coder:1.5b
    )
)

REM --- 2. Start Backend on port 8000 ---
echo [RepoMedic] Starting backend API (uvicorn) on http://127.0.0.1:8000 ...
start "RepoMedic Backend" /MIN cmd /c "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1"

REM --- 3. Start Frontend on port 5173 ---
echo [RepoMedic] Starting frontend UI (Vite) on http://localhost:5173 ...
start "RepoMedic Frontend" /MIN cmd /c "cd /d ""%~dp0frontend"" && npm.cmd run dev > frontend.log 2>&1"

REM --- 4. Wait up to 15s for Vite (:5173) to accept connections ---
echo [RepoMedic] Waiting for frontend server on port 5173...
for /L %%i in (1,1,15) do (
    curl -s http://127.0.0.1:5173 >nul 2>&1
    if not errorlevel 1 goto :ready
    timeout /t 1 /nobreak >nul
)

:ready
echo [RepoMedic] Opening http://localhost:5173 ...
start "" "http://localhost:5173"

echo.
echo [RepoMedic] ========================================
echo [RepoMedic] RepoMedic is running!
echo [RepoMedic]   Web UI:      http://localhost:5173
echo [RepoMedic]   API Docs:    http://localhost:8000/docs
echo [RepoMedic]   Backend log: backend\backend.log
echo [RepoMedic]   Frontend log: frontend\frontend.log
echo [RepoMedic] ========================================
