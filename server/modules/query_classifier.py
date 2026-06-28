from enum import Enum

class QueryMode(str, Enum):
    RAG_ONLY = "rag_only"
    SQL_ONLY = "sql_only"
    HYBRID = "hybrid"

SQL_KEYWORDS = [
    "my",
    "mine",
    "average",
    "recent",
    "last",
    "past",
    "data",
    "reading",
    "readings",
    "measurement",
    "measurements",
    "personal",
]

RAG_KEYWORDS = [
    "what is",
    "what's",
    "whats",
    "what are",
    "what does",
    "what do",
    "definition",
    "define",
    "explain",
    "meaning",
    "how does",
    "how do",
    "tell me about",
    "why does",
    "why do",
    "related",
    "sleep",
    "stress",
]

def classify_query(question: str) -> QueryMode:
    q = question.lower()
    has_sql = any(k in q for k in SQL_KEYWORDS)
    has_rag = any(k in q for k in RAG_KEYWORDS)

    if has_sql and has_rag:
        return QueryMode.HYBRID
    if has_sql:
        return QueryMode.SQL_ONLY
    return QueryMode.RAG_ONLY

def infer_days(question: str) -> int | None:
    q = question.lower()

    if "yesterday" in q:
        return 1
    if "last week" in q or "past week" in q:
        return 7
    if "last month" in q or "past month" in q or "30 days" in q:
        return 30

    return 30