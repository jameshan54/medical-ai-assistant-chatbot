from langchain_core.tools import tool
from sqlalchemy.orm import Session

from modules.rag_handlers import search_research_docs as fetch_research_docs
from modules.sql_handlers import build_sql_context


class ToolRunContext:
    def __init__(self):
        self.sources: list[str] = []


def make_tools(db: Session, participant_code: str, ctx: ToolRunContext):
    @tool
    def query_hrv_data() -> str:
        """Fetch summarized personal HRV data for the current study participant (last 90 days).
        Use when the user asks about their own RMSSD, averages, recent readings, etc."""
        return build_sql_context(db, participant_code, days=90)

    @tool
    def search_research_docs(query: str) -> str:
        """Search uploaded research papers for HRV concepts, definitions, sleep/stress links, etc.
        Use when the user asks what/why/how about HRV science — not personal numbers."""
        context, sources = fetch_research_docs(query)
        ctx.sources = sources
        return context

    return [query_hrv_data, search_research_docs]