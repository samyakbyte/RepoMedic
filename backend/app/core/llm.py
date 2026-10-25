"""LLM service: local model via Ollama (no hosted AI, ever)."""

import json
import time
from typing import Optional

import httpx

from app.config import (
    LLM_TIMEOUT_S,
    NUM_CTX,
    NUM_PREDICT,
    OLLAMA_BASE_URL,
    REPOMEDIC_MODEL,
    SEED,
    TEMPERATURE,
)
from app.schemas.patch import RepairProposal

VALIDATION_ERROR_APPEND_LIMIT = 2  # retries after the first generation attempt

SYSTEM_PROMPT = """You are a code-repair engine running offline. You receive a failing
Python test and the relevant source code. Your job is to propose a minimal
search/replace patch that fixes the bug.

Output ONLY valid JSON matching the provided schema. No markdown fences, no
intro, no extra text.

Rules:
- old_snippet must be copied verbatim and exactly from the provided source,
  including indentation. Make it as small as possible while still unique.
- new_snippet is the corrected replacement.
- Never change test files.
- Change the minimum necessary.

Example (generic, unrelated to any RepoMedic demo project):

Input source:
def is_even(n):
    return n % 2 == 1   # bug: odd numbers reported as even

Correct output JSON:
{"root_cause": "parity test is inverted", "target_file": "src/example.py",
 "old_snippet": "return n % 2 == 1", "new_snippet": "return n % 2 == 0",
 "explanation": "n % 2 == 0 is True exactly for even numbers",
 "expected_outcome": "is_even(2) is True and is_even(3) is False"}
"""


class OllamaError(Exception):
    def __init__(self, code: str, message: str, hint: str):
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(message)


class LLMResult:
    def __init__(
        self,
        proposal: RepairProposal,
        model: str,
        duration_s: float,
        prompt_eval_count: Optional[int],
        eval_count: Optional[int],
        eval_duration_ns: Optional[int],
        total_duration_ns: Optional[int],
        load_duration_ns: Optional[int],
    ):
        self.proposal = proposal
        self.model = model
        self.duration_s = duration_s
        self.prompt_eval_count = prompt_eval_count
        self.eval_count = eval_count
        self.eval_duration_ns = eval_duration_ns
        self.total_duration_ns = total_duration_ns
        self.load_duration_ns = load_duration_ns
        if eval_count and eval_duration_ns:
            self.tokens_per_second = eval_count / (eval_duration_ns / 1e9)
        else:
            self.tokens_per_second = None


class OllamaClient:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = REPOMEDIC_MODEL,
        temperature: float = TEMPERATURE,
        seed: int = SEED,
        num_ctx: int = NUM_CTX,
        num_predict: int = NUM_PREDICT,
        timeout_s: float = LLM_TIMEOUT_S,
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout_s = timeout_s

    # -- health -----------------------------------------------------------

    def health(self) -> dict:
        """Return {ollama_reachable, model_available, model, parameter_size,
        quantization, family}."""
        reachable = False
        model_available = False
        detail: dict = {}
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                reachable = True
                tags = resp.json()
                models = [m.get("name", "") for m in tags.get("models", [])]
                model_available = any(m == self.model or m.startswith(self.model + ":") for m in models)
        except httpx.ConnectError:
            return {
                "ollama_reachable": False,
                "model_available": False,
                "model": self.model,
                "parameter_size": None,
                "quantization": None,
                "family": None,
                "hint": "Ollama is not reachable. Start it with 'ollama serve' or install Ollama from https://ollama.com",
            }
        except httpx.RequestError as exc:
            return {
                "ollama_reachable": False,
                "model_available": False,
                "model": self.model,
                "parameter_size": None,
                "quantization": None,
                "family": None,
                "hint": f"Could not talk to Ollama: {exc}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ollama_reachable": False,
                "model_available": False,
                "model": self.model,
                "parameter_size": None,
                "quantization": None,
                "family": None,
                "hint": f"Ollama health check failed: {exc}",
            }

        if model_available:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(f"{self.base_url}/api/show", json={"name": self.model})
                    if resp.status_code == 200:
                        info = resp.json()
                        mod = info.get("modelinfo", {}) or {}
                        detail = {
                            "parameter_size": info.get("parameter_size") or mod.get("general.parameter_size"),
                            "quantization": info.get("quantization") or mod.get("general.quantization"),
                            "family": info.get("family") or mod.get("general.family") or self.model.split(":")[0],
                        }
            except Exception:
                pass

        return {
            "ollama_reachable": True,
            "model_available": model_available,
            "model": self.model,
            "parameter_size": detail.get("parameter_size"),
            "quantization": detail.get("quantization"),
            "family": detail.get("family"),
            "hint": None if model_available else f"Model '{self.model}' not pulled. Run: ollama pull {self.model}",
        }

    # -- generation --------------------------------------------------------

    def generate_repair(self, context: str) -> LLMResult:
        """Generate a RepairProposal via POST /api/chat with JSON schema."""
        schema = json.dumps(RepairProposal.model_json_schema())
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
            "keep_alive": "10m",
        }

        last_error: Optional[str] = None
        attempt = 0
        max_attempts = 1 + VALIDATION_ERROR_APPEND_LIMIT  # initial + 2 retries

        while attempt < max_attempts:
            attempt += 1
            start = time.perf_counter()
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    resp = client.post(f"{self.base_url}/api/chat", json=payload)
            except httpx.ConnectError as exc:
                raise OllamaError(
                    "OLLAMA_DOWN",
                    "Ollama is not reachable",
                    f"Start Ollama (e.g. 'ollama serve') and confirm {self.base_url} responds. Underlying: {exc}",
                ) from exc
            except httpx.TimeoutException as exc:
                raise OllamaError(
                    "LLM_TIMEOUT",
                    f"Model generation timed out after {self.timeout_s}s",
                    "Try a smaller model, raise REPOMEDIC_LLM_TIMEOUT_S, or free GPU RAM",
                ) from exc
            except httpx.RequestError as exc:
                raise OllamaError(
                    "LLM_REQUEST_ERROR",
                    f"Request to Ollama failed: {exc}",
                    "Check that Ollama is running and the model is pulled",
                ) from exc

            duration_s = time.perf_counter() - start

            if resp.status_code == 404:
                raise OllamaError(
                    "MODEL_NOT_PULLED",
                    f"Model '{self.model}' is not available in Ollama",
                    f"Run: ollama pull {self.model}",
                )
            if resp.status_code >= 500:
                text = resp.text[:500]
                if "out of memory" in text.lower() or "oom" in text.lower():
                    raise OllamaError(
                        "LLM_OOM",
                        "Ollama ran out of memory while generating",
                        "Use a smaller model (qwen2.5-coder:1.5b) or lower NUM_CTX/NUM_PREDICT",
                    )
                raise OllamaError(
                    "OLLAMA_ERROR",
                    f"Ollama returned HTTP {resp.status_code}: {text}",
                    "Check 'ollama ps' and Ollama logs",
                )

            resp.raise_for_status()

            try:
                data = resp.json()
            except json.JSONDecodeError as exc:
                last_error = f"Non-JSON response from Ollama: {exc}"
                if attempt < max_attempts:
                    payload["messages"] = messages + [
                        {"role": "user", "content": f"Your previous response was not valid JSON. Error: {last_error}. Reply with ONLY valid JSON matching the schema."}
                    ]
                    continue
                raise OllamaError("LLM_INVALID_OUTPUT", last_error, "The model did not return usable JSON; try again or simplify the context")

            content = data.get("message", {}).get("content", "") or ""
            # Ollama may wrap the JSON in markdown fences even with format:json; strip them.
            content = self._strip_fences(content)

            try:
                proposal = RepairProposal.model_validate_json(content)
            except Exception as exc:
                last_error = f"Invalid or schema-mismatch output: {exc}"
                if attempt < max_attempts:
                    payload["messages"] = messages + [
                        {"role": "user", "content": f"Your previous response failed validation: {last_error}. Reply with ONLY valid JSON matching the schema."}
                    ]
                    continue
                raise OllamaError("LLM_INVALID_OUTPUT", last_error, "The model output did not match the repair schema; try again")

            # Metrics from Ollama's own counters (never wall-clock derived).
            return LLMResult(
                proposal=proposal,
                model=data.get("model", self.model),
                duration_s=duration_s,
                prompt_eval_count=data.get("prompt_eval_count"),
                eval_count=data.get("eval_count"),
                eval_duration_ns=data.get("eval_duration"),
                total_duration_ns=data.get("total_duration"),
                load_duration_ns=data.get("load_duration"),
            )

        # Unreachable, but keep mypy happy.
        raise OllamaError("LLM_INVALID_OUTPUT", last_error or "invalid output", "The model did not return usable JSON")

    @staticmethod
    def _strip_fences(content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            # drop opening fence
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return content
