from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    question: str
    jd_text: str
    resume_text: str
    custom_prompt_text: Optional[str] = None
    model: str
    judge_strictness: int = Field(default=3, ge=1, le=5)
    max_retries: int = Field(default=2, ge=0, le=5)


class StepState(BaseModel):
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
    output_json: Optional[Dict[str, Any]] = None
    output_text: Optional[str] = None
    error: Optional[str] = None


class JudgeReport(BaseModel):
    score: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)
    fixes: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class AttemptSummary(BaseModel):
    attempt: int
    steps: Dict[str, StepState]
    final_output: Optional[str] = None
    judge_report: Optional[JudgeReport] = None


class RunState(BaseModel):
    run_id: str
    status: Literal["queued", "running", "done", "failed", "canceled"] = "queued"
    current_step: Optional[int] = None
    attempt: int = 1
    steps: Dict[str, StepState]
    final_output: Optional[str] = None
    judge_report: Optional[JudgeReport] = None
    attempt_history: List[AttemptSummary] = Field(default_factory=list)
    error: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str


class ModelsResponse(BaseModel):
    models: List[str]
    error: Optional[str] = None
