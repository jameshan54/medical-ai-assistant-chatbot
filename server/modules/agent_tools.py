from langchain_core.tools import tool
from sqlalchemy.orm import Session

from modules.rag_handlers import search_research_docs as fetch_research_docs
from modules.sql_handlers import build_sql_result, format_sql_result
from modules.trace_collector import TraceCollector


def make_tools(
    db: Session,
    participant_code: str,
    trace_collector: TraceCollector | None = None,
):
    @tool
    def query_hrv_data() -> str:
        """Fetch summarized personal HRV data for the current study participant (last 90 days).
        Call at most once. Use for the user's own RMSSD, averages, recent readings, or counts.
        Do not use for symptoms, chest pain, diagnosis, or medication questions."""
        result = build_sql_result(db, participant_code, days=90)
        text = format_sql_result(result)
        if trace_collector is not None:
            trace_collector.sql_result = result
            trace_collector.sql_text = text
            trace_collector.record_tool_call("query_hrv_data", days=90)
        return text

    @tool
    def search_research_docs(query: str) -> str:
        """Search uploaded research papers once for HRV concepts, definitions, sleep/stress, caffeine, etc.
        Pass a single focused query. Do not call again with a rephrased query.
        Answer only from the returned text; do not invent findings not in the snippets.
        Use for what/why/how about HRV science — not personal numbers, symptoms, or medication."""
        context, sources, chunks = fetch_research_docs(query)
        if trace_collector is not None:
            trace_collector.sources = sources
            trace_collector.rag_chunks = chunks
            trace_collector.record_tool_call(
                "search_research_docs",
                query=query,
                n_chunks=len(chunks),
            )
        return context

    return [query_hrv_data, search_research_docs]