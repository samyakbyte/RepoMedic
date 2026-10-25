"""Configuration read from environment variables with sensible defaults.

Copy .env.example to .env and adjust as needed. All values are read here,
the rest of the app imports from this module only.
"""
import os
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


# Ollama / model settings
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
REPOMEDIC_MODEL = _env("REPOMEDIC_MODEL", "qwen2.5-coder:1.5b")
REPOMEDIC_TEMPERATURE = float(_env("REPOMEDIC_TEMPERATURE", "0"))
REPOMEDIC_SEED = int(_env("REPOMEDIC_SEED", "42"))
REPOMEDIC_NUM_CTX = int(_env("REPOMEDIC_NUM_CTX", "4096"))
REPOMEDIC_NUM_PREDICT = int(_env("REPOMEDIC_NUM_PREDICT", "768"))
REPOMEDIC_LLM_TIMEOUT_S = float(_env("REPOMEDIC_LLM_TIMEOUT_S", "120"))

# Verification settings
REPOMEDIC_PYTEST_TIMEOUT_S = float(_env("REPOMEDIC_PYTEST_TIMEOUT_S", "30"))

# Repair loop limits
REPOMEDIC_MAX_ATTEMPTS = int(_env("REPOMEDIC_MAX_ATTEMPTS", "2"))
REPOMEDIC_MAX_CONTEXT_CHARS = int(_env("REPOMEDIC_MAX_CONTEXT_CHARS", "6000"))

# Data directory (runtime workspaces, sessions, reports — git-ignored)
DATA_DIR = Path(_env("REPOMEDIC_DATA_DIR", "./data")).resolve()
WORKSPACES_DIR = DATA_DIR / "workspaces"
SESSIONS_DIR = DATA_DIR / "sessions"
REPORTS_DIR = DATA_DIR / "reports"
BACKUPS_DIR = DATA_DIR / "backups"

for _dir in (DATA_DIR, WORKSPACES_DIR, SESSIONS_DIR, REPORTS_DIR, BACKUPS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

APP_VERSION = "0.1.0"
APP_NAME = "repomedic"

# CORS origins allowed to call the API (frontend dev servers)
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# Files that are never patchable by the model (protected fixtures)
PROTECTED_NAMES = {
    "conftest.py",
    "pytest.ini",
    "project.json",
    "setup.py",
    "pyproject.toml",
    "tox.ini",
    ".env",
}
PROTECTED_SUFFIXES = ("requirements.txt", "requirements.in")

# Patch size limits so patches stay targeted
MAX_SNIPPET_CHARS = 2000
MAX_CHANGED_LINES = 40

# Output capture cap for pytest runs (chars)
MAX_CAPTURE_CHARS = 20000

# Convenience aliases matching env names
MODEL = REPOMEDIC_MODEL
TEMPERATURE = REPOMEDIC_TEMPERATURE
SEED = REPOMEDIC_SEED
NUM_CTX = REPOMEDIC_NUM_CTX
NUM_PREDICT = REPOMEDIC_NUM_PREDICT
LLM_TIMEOUT_S = REPOMEDIC_LLM_TIMEOUT_S
PYTEST_TIMEOUT_S = REPOMEDIC_PYTEST_TIMEOUT_S
MAX_ATTEMPTS = REPOMEDIC_MAX_ATTEMPTS
MAX_CONTEXT_CHARS = REPOMEDIC_MAX_CONTEXT_CHARS
