# Troubleshooting

## 1. `localhost:5173` says "Can't reach this page" / `ERR_CONNECTION_REFUSED`
- Make sure **Node.js** is installed (`node -v` and `npm -v` in `cmd.exe`) and that you ran **`setup.bat`** first so `frontend\node_modules` exists.
- Check `frontend\frontend.log` for port conflicts or npm errors.
- To run Vite manually and see live terminal output:
  ```bat
  cd frontend
  npm run dev
  ```

## 2. Windows popup: `Windows cannot find 'C:\Program Files\Ollama\ollama.exe'`
- Fixed in `start.bat`: Windows installs Ollama per-user under `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` by default, and `start.bat` now checks `if exist` safely before starting it.
- If Ollama isn't installed yet, download it from <https://ollama.com/download> and run:
  ```bat
  ollama pull qwen2.5-coder:1.5b
  ```

## 3. UI banner shows "Model Missing: qwen2.5-coder:1.5b"
- Ollama is running, but the coding model hasn't been downloaded yet. Run:
  ```bat
  ollama pull qwen2.5-coder:1.5b
  ```
  The status pill in the top-right corner of the UI will automatically turn green within 10 seconds.

## 4. PowerShell says `running scripts is disabled on this system`
- Either use **Command Prompt (`cmd.exe`)** or invoke the venv Python binary directly without `activate.ps1`:
  ```powershell
  .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
  ```
