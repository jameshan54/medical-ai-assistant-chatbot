"""Env-based LangSmith tracing. Missing keys warn and continue — never fail startup."""

from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from logger import logger

_SERVER_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_SERVER_ROOT / ".env")

DEFAULT_PROJECT = "medical-ai-assistant"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"true", "1", "yes"}


def tracing_requested() -> bool:
    return _truthy(os.getenv("LANGSMITH_TRACING")) or _truthy(
        os.getenv("LANGCHAIN_TRACING_V2")
    )


def _api_key() -> str | None:
    return os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")


def agent_run_config(
    *,
    run_name: str = "hrv_agent",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LangChain invoke config so traces are filterable in LangSmith."""
    return {
        "run_name": run_name,
        "tags": list(tags or []),
        "metadata": dict(metadata or {}),
    }


def without_tracing():
    """Disable LangSmith for nested LLM calls (RAGAS / judge)."""
    try:
        from langsmith import tracing_context

        return tracing_context(enabled=False)
    except ImportError:
        return nullcontext()


def init_langsmith() -> dict[str, Any]:
    """Enable auto-trace when env asks for it. Warn + disable if the API key is missing."""
    if not tracing_requested():
        return {"enabled": False, "reason": "tracing_off", "project": None}

    api_key = _api_key()
    if not api_key:
        logger.warning(
            "LangSmith tracing requested but LANGSMITH_API_KEY is missing; "
            "continuing without tracing"
        )
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return {"enabled": False, "reason": "missing_api_key", "project": None}

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if not os.getenv("LANGSMITH_API_KEY") and os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGSMITH_API_KEY"] = os.environ["LANGCHAIN_API_KEY"]

    project = (
        os.getenv("LANGSMITH_PROJECT")
        or os.getenv("LANGCHAIN_PROJECT")
        or DEFAULT_PROJECT
    )
    os.environ["LANGSMITH_PROJECT"] = project

    try:
        from langsmith import Client

        Client()
    except Exception as exc:  # noqa: BLE001 — optional health check
        logger.warning("LangSmith client init warning (tracing still enabled): %s", exc)

    logger.info("LangSmith tracing enabled (project=%s)", project)
    return {"enabled": True, "reason": "ok", "project": project}
