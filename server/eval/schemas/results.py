"""Eval result score schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RoutingScore(BaseModel):
    exact_match: bool
    precision: float
    recall: float
    f1: float
    unnecessary_tools: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)


class SqlScore(BaseModel):
    skipped: bool = False
    passed: bool | None = None
    details: dict[str, bool | None] = Field(default_factory=dict)
    reason: str | None = None


class RagScore(BaseModel):
    skipped: bool = False
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    answer_correctness: float | None = None
    errors: dict[str, str] = Field(default_factory=dict)
    reason: str | None = None


class FinalAnswerJudgment(BaseModel):
    data_accuracy: int = Field(ge=1, le=5)
    evidence_groundedness: int = Field(ge=1, le=5)
    answer_relevance: int = Field(ge=1, le=5)
    safety: int = Field(ge=1, le=5)
    overall_quality: int = Field(ge=1, le=5)
    reasoning: str


class FinalAnswerScore(BaseModel):
    skipped: bool = False
    judgment: FinalAnswerJudgment | None = None
    safety_pass: bool | None = None
    reason: str | None = None
    error: str | None = None
