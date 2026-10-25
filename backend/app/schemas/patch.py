"""Patch schema: the structured repair proposal the LLM must emit."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class RepairProposal(BaseModel):
    """A single search/replace patch proposed by the local model."""

    root_cause: str = Field(..., min_length=1, max_length=400, description="One-sentence root cause (1-400 chars).")
    target_file: str = Field(..., min_length=1, max_length=200, description="File to patch, relative to workspace root, e.g. src/calc.py.")
    old_snippet: str = Field(..., min_length=1, max_length=2000, description="Existing code to replace, copied verbatim including indentation.")
    new_snippet: str = Field(..., min_length=1, max_length=2000, description="Corrected replacement code.")
    explanation: str = Field(..., min_length=1, max_length=1000, description="Human-readable explanation of the fix.")
    expected_outcome: str = Field(..., min_length=1, max_length=1000, description="What should hold after the patch is applied.")

    @model_validator(mode="after")
    def _not_a_noop(self) -> "RepairProposal":
        if self.old_snippet == self.new_snippet:
            raise ValueError("old_snippet and new_snippet must differ")
        return self

    def to_json_schema(self) -> dict:
        return self.model_json_schema()


class PatchValidationResult(BaseModel):
    ok: bool = False
    codes: list[str] = Field(default_factory=list)
    snippet_normalized: bool = False
    diff: Optional[str] = None
    before: str = ""
    after: str = ""
    old_snippet_found_at: Optional[int] = None  # line index (0-based) where old_snippet starts


class PatchApplyResult(BaseModel):
    ok: bool
    backup_path: Optional[str] = None
    sha_before: Optional[str] = None
    sha_after: Optional[str] = None
    target_file: str = ""
