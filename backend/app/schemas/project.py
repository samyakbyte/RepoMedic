"""Demo project model."""

from typing import List

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    description: str
    bug_category: str
    failing_test: str = Field(..., description='Test id that fails before repair, e.g. "tests/test_calc.py::test_apply_discount_partial"')
    test_command: List[str] = Field(default=["pytest", "-q", "tests"])
    target_files: List[str] = Field(..., description="Source files the model is allowed to patch")
