"""Compatibility shims so ragas 0.4.3 can import with modern langchain-community."""

from __future__ import annotations

import sys
import types


def ensure_ragas_importable() -> None:
    """Stub removed langchain_community.chat_models.vertexai path (ragas 0.4.3 bug)."""
    name = "langchain_community.chat_models.vertexai"
    if name in sys.modules:
        return

    mod = types.ModuleType(name)

    class ChatVertexAI:  # noqa: N801 — match upstream symbol name
        """Placeholder; VertexAI is unused by this project."""

    mod.ChatVertexAI = ChatVertexAI
    sys.modules[name] = mod
