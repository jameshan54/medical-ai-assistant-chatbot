"""RAGAS-based RAG metrics (Groq LLM + Gemini embeddings)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from server.eval.metrics._ragas_compat import ensure_ragas_importable
from server.eval.schemas.dataset import EvalExample
from server.eval.schemas.results import RagScore

_SERVER_ROOT = Path(__file__).resolve().parents[2]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from dotenv import load_dotenv

load_dotenv(_SERVER_ROOT / ".env")


def _contexts_from_trace(trace: dict[str, Any] | None) -> list[str]:
    if not trace:
        return []
    chunks = trace.get("rag_chunks") or []
    texts: list[str] = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            text = chunk.get("text") or ""
        else:
            text = str(chunk)
        if text:
            texts.append(text)
    return texts


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def score_rag(
    example: EvalExample,
    *,
    answer: str,
    trace: dict[str, Any] | None,
    actual_tools: list[str] | None = None,
) -> RagScore:
    """Score RAG quality when RAG tool was used or category expects RAG."""
    tools = set(actual_tools or [])
    needs_rag = (
        "search_research_docs" in tools
        or example.category in ("rag_only", "hybrid")
    )
    if not needs_rag:
        return RagScore(skipped=True, reason="not_applicable")

    contexts = _contexts_from_trace(trace)
    if not contexts:
        return RagScore(
            skipped=False,
            reason="missing_rag_contexts",
            errors={"contexts": "no rag_chunks in trace"},
        )

    ensure_ragas_importable()

    try:
        from datasets import Dataset
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_groq import ChatGroq
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            answer_correctness,
            answer_relevancy,
            context_precision,
            faithfulness,
        )
    except Exception as exc:  # noqa: BLE001 — surface import/runtime setup errors
        return RagScore(skipped=False, reason="ragas_unavailable", errors={"import": str(exc)})

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return RagScore(
            skipped=False,
            reason="missing_groq_api_key",
            errors={"env": "GROQ_API_KEY not set"},
        )

    judge_model = os.getenv("GROQ_JUDGE_MODEL", os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b"))
    llm = LangchainLLMWrapper(
        ChatGroq(groq_api_key=groq_key, model_name=judge_model, temperature=0)
    )
    embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    )

    reference = example.reference_answer
    row: dict[str, Any] = {
        "user_input": example.question,
        "response": answer or "",
        "retrieved_contexts": contexts,
    }
    # Groq rejects n>1; answer_relevancy default strictness=3 requests multiple samples.
    answer_relevancy.strictness = 1
    metrics = [faithfulness, answer_relevancy]
    if reference:
        row["reference"] = reference
        metrics.extend([context_precision, answer_correctness])

    dataset = Dataset.from_list([row])
    errors: dict[str, str] = {}
    scores: dict[str, float | None] = {
        "faithfulness": None,
        "answer_relevancy": None,
        "context_precision": None,
        "answer_correctness": None,
    }

    try:
        result = evaluate(
            dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings,
            raise_exceptions=False,
            show_progress=False,
            batch_size=1,
        )
        # EvaluationResult supports dict-like access / to_pandas
        try:
            pdf = result.to_pandas()
            record = pdf.iloc[0].to_dict()
        except Exception:
            record = dict(result) if hasattr(result, "items") else {}

        for key in scores:
            if key in record:
                scores[key] = _to_float(record.get(key))
    except Exception as exc:  # noqa: BLE001
        errors["evaluate"] = str(exc)

    return RagScore(
        skipped=False,
        faithfulness=scores["faithfulness"],
        answer_relevancy=scores["answer_relevancy"],
        context_precision=scores["context_precision"],
        answer_correctness=scores["answer_correctness"],
        errors=errors,
        reason="ok" if not errors else "partial_or_failed",
    )
