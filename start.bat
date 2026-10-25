@echo off
REM RepoMedic launch script: starts Ollama (if possible), backend (port 8000),
REM frontend (port 5173), and opens the UI in the default browser.
REM Run: start.bat   (after setup.bat)

cd /d "%~dp0"

echo [RepoMedic] ========================================
echo [RepoMedic]  Starting RepoMedic
echo [RepoMedic] ========================================

REM --- 1. Ollama ---
echo [RepoMedic] Checking Ollama...
where ollama >nul 2>nul
if %errorlevel% equ 0 (
    echo [RepoMedic] Ollama found on PATH.
) else (
    echo [RepoMedic] Ollama not on PATH. Trying to start the installed Ollama service...
    start "" /B "%ProgramFiles%\Ollama\ollama.exe" serve >nul 2>&1
    timeout /t 3 >nul
    where ollama >nul 2>nul
    if %errorlevel% neq 0 (
        echo [RepoMedic] WARNING: Ollama is not running. The UI will show "Model offline".
        echo [RepoMedic]          Fix: open a Terminal and run: ollama serve
        echo [RepoMedic]          Then pull a model: ollama pull qwen2.5-coder:1.5b
    )
)

REM --- 2. Backend ---
echo [RepoMedic] Activating backend virtual environment...
call backend\.venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [RepoMedic] ERROR: backend venv not found. Run setup.bat first.
    exit /b 1
)

echo [RepoMedic] Starting backend (uvicorn) on port 8000...
start "" /B cmd /c "cd /d %~dp0\backend && uvicorn app.main:app --port 8000 > backend.log 2>&1"

timeout /t 4 >nul
echo [RepoMedic] Backend log: backend\backend.log

REM --- 3. Frontend ---
echo [RepoMedic] Starting frontend (Vite) on port 5173...
start "" cmd /c "cd /d %~dp0\frontend && npm run dev > frontend.log 2>&1"

timeout /t 6 >nul
echo [RepoMedic] Frontend log: frontend\frontend.log

REM --- 4. Open browser ---
echo [RepoMedic] Opening http://localhost:5173
start http://localhost:5173

echo [RepoMedic] ========================================
echo [RepoMedic] RepoMedic is running.
echo [RepoMedic]   UI:          http://localhost:5173
echo [RepoMedic]   API docs:    http://localhost:8000/docs
echo [RepoMedic]   Backend log: backend\backend.log
echo [RepoMedic]   Frontend log: frontend\frontend.log
echo [RepoMedic] ========================================
