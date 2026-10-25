"""Application singletons: one shared store, LLM client, context builder, etc."""

from pathlib import Path

from app.config import (
    CORS_ORIGINS,
    LLM_TIMEOUT_S,
    MAX_CONTEXT_CHARS,
    MODEL,
    NUM_CTX,
    NUM_PREDICT,
    OLLAMA_BASE_URL,
    SEED,
    TEMPERATURE,
)
from app.core.context import ContextBuilder
from app.core.llm import OllamaClient
from app.core.state_machine import SessionStore
from app.core.verification import Verifier
from app.core.workspace import WorkspaceManager

ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_PROJECTS_DIR = ROOT / "demo-projects"
BENCHMARK_RESULTS_DIR = ROOT / "benchmarks" / "results"

workspace_manager = WorkspaceManager(DEMO_PROJECTS_DIR)
store = SessionStore(workspace_manager)
llm_client = OllamaClient(
    base_url=OLLAMA_BASE_URL,
    model=MODEL,
    temperature=TEMPERATURE,
    seed=SEED,
    num_ctx=NUM_CTX,
    num_predict=NUM_PREDICT,
    timeout_s=LLM_TIMEOUT_S,
)
context_builder = ContextBuilder(max_chars=MAX_CONTEXT_CHARS)
verifier = Verifier()

__all__ = [
    "workspace_manager",
    "store",
    "llm_client",
    "context_builder",
    "verifier",
    "ROOT",
    "DEMO_PROJECTS_DIR",
    "BENCHMARK_RESULTS_DIR",
]
