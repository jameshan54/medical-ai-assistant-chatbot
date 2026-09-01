from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TraceCollector:
    """Per-request / per-eval-example trace buffer.

    Do not store this as a module-level singleton with mutable data.
    Create a new instance for each /ask/ request or eval example.
    """

    sources: list[str] = field(default_factory=list)
    rag_chunks: list[dict[str, Any]] = field(default_factory=list)
    sql_result: dict[str, Any] | None = None
    sql_text: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def record_tool_call(self, name: str, **payload: Any) -> None:
        self.tool_calls.append({"name": name, **payload})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_trace_ctx: ContextVar[TraceCollector | None] = ContextVar(
    "trace_collector",
    default=None,
)


def get_trace_collector() -> TraceCollector | None:
    return _trace_ctx.get()


def set_trace_collector(collector: TraceCollector | None) -> Token:
    return _trace_ctx.set(collector)


def reset_trace_collector(token: Token) -> None:
    _trace_ctx.reset(token)