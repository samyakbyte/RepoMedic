# Setup & Configuration Guide

## Requirements

- **Python**: 3.10 or newer
- **Node.js**: 18 LTS or newer (includes `npm`)
- **Ollama**: Latest desktop/CLI release from <https://ollama.com>
- **Default Model**: `qwen2.5-coder:1.5b` (`ollama pull qwen2.5-coder:1.5b`)

## Environment Variables (`.env`)

Copy `.env.example` to `.env` at the repository root (done automatically by `setup.bat`):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama HTTP endpoint |
| `REPOMEDIC_MODEL` | `qwen2.5-coder:1.5b` | Ollama model tag used for repair |
| `REPOMEDIC_TEMPERATURE` | `0` | Sampling temperature (`0` for deterministic patches) |
| `REPOMEDIC_SEED` | `42` | Random seed passed to Ollama |
| `REPOMEDIC_NUM_CTX` | `4096` | Context window tokens |
| `REPOMEDIC_NUM_PREDICT` | `768` | Max completion tokens |
| `REPOMEDIC_LLM_TIMEOUT_S` | `120` | Timeout in seconds per Ollama generation request |
| `REPOMEDIC_PYTEST_TIMEOUT_S` | `30` | Timeout in seconds per pytest execution |
| `REPOMEDIC_MAX_ATTEMPTS` | `2` | Max repair attempts per session |
| `REPOMEDIC_MAX_CONTEXT_CHARS` | `6000` | Upper bound on prompt context size |
| `REPOMEDIC_DATA_DIR` | `<repo_root>/data` | Directory for sandboxes, backups, sessions, and reports |
