from fastapi import APIRouter, Form, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from modules.llm import get_llm_chain
from modules.query_handlers import query_chain
from modules.db import get_db
from modules.sql_handlers import build_sql_context
from modules.query_classifier import classify_query, infer_days, QueryMode
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone
from pydantic import Field
from typing import List, Optional
from logger import logger
import os

router = APIRouter()


class SimpleRetriever(BaseRetriever):
    tags: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[dict] = Field(default_factory=dict)

    def __init__(self, documents: List[Document]):
        super().__init__()
        self._docs = documents

    def _get_relevant_documents(self, query: str) -> List[Document]:
        return self._docs


def search_pinecone(question: str) -> list[Document]:
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(os.environ["PINECONE_INDEX_NAME"])
    embed_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    embedded_query = embed_model.embed_query(question)
    res = index.query(vector=embedded_query, top_k=3, include_metadata=True)

    return [
        Document(
            page_content=match["metadata"].get("text", ""),
            metadata=match["metadata"],
        )
        for match in res["matches"]
    ]


@router.post("/ask/")
async def ask_question(
    question: str = Form(...),
    participant_code: str = Form("P001"),
    db: Session = Depends(get_db),
):
    try:
        logger.info(f"user query: {question} (participant={participant_code})")

        mode = classify_query(question)
        days = infer_days(question)
        logger.info(f"query mode: {mode.value}, days: {days}")

        if mode in (QueryMode.SQL_ONLY, QueryMode.HYBRID):
            sql_context = build_sql_context(db, participant_code, days=days)
        else:
            sql_context = "Not applicable for this question."

        if mode == QueryMode.SQL_ONLY:
            docs = []
        else:
            docs = search_pinecone(question)

        retriever = SimpleRetriever(docs)
        chain = get_llm_chain(retriever, sql_context=sql_context)
        result = query_chain(chain, question)
        result["mode"] = mode.value

        logger.info("query successful")
        return result

    except Exception as e:
        logger.exception("Error processing question")
        return JSONResponse(status_code=500, content={"error": str(e)})