"""
evaluate.py

Runs fixed test questions through the RAG chain and saves outputs for manual
RAG evaluation.

Outputs:
1. CSV summary: question, answer, source list, chunk references, and blank human-eval columns
2. JSONL detail: full retrieved chunk text + metadata for each question

Usage:
    python evaluate.py
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from pinecone import Pinecone
from pydantic import Field, PrivateAttr
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from llm import get_llm_chain

load_dotenv()

TOP_K = int(os.getenv("RAG_TOP_K", "5"))
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "medicalindex")


class SimpleRetriever(BaseRetriever):
    tags: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[dict] = Field(default_factory=dict)
    _docs: List[Document] = PrivateAttr(default_factory=list)

    def __init__(self, documents: List[Document]):
        super().__init__()
        self._docs = documents

    def _get_relevant_documents(self, query: str) -> List[Document]:
        return self._docs


def build_retriever(question: str, embed_model, index, top_k: int = TOP_K) -> SimpleRetriever:
    """Embed query, retrieve top-k matches from Pinecone, and preserve scores."""
    embedded_query = embed_model.embed_query(question)
    res = index.query(
        vector=embedded_query,
        top_k=top_k,
        include_metadata=True,
    )

    docs = []
    for rank, match in enumerate(res.get("matches", []), start=1):
        metadata = dict(match.get("metadata") or {})
        metadata["score"] = match.get("score")
        metadata["rank"] = rank

        docs.append(Document(
            page_content=metadata.get("text", ""),
            metadata=metadata,
        ))

    return SimpleRetriever(docs)


TEST_QUESTIONS = [
    # General
    "What is HRV?",
    "What's the difference between RMSSD and SDNN?",
    "What's considered a normal HRV range?",
    "How does poor sleep affect HRV?",
    "Why does stress lower HRV?",
    "Can wearable devices accurately measure HRV?",
    # Multi-source
    "Does acute stress affect HRV differently than chronic stress?",
    "Can HRV measurement error affect how we interpret stress-related HRV changes?",
    # Out-of-scope
    "My heart rate is really high, could something be wrong with my heart?",
    "Should I go to the doctor for this symptom?",
    "What's the weather like today?",
    # Unanswerable
    "How does HRV change during pregnancy?",
    "Does caffeine affect HRV?",
    # Edge case
    "Lower HRV is better, right?",
    "whats the diff btwn sdnn and rmssd lol",
]


def make_chunk_reference(chunks: List[dict]) -> str:
    """Compact reference string for CSV review."""
    refs = []
    for c in chunks:
        score = c.get("score")
        score_text = f", score={score:.4f}" if isinstance(score, (int, float)) else ""
        refs.append(
            f"rank={c.get('rank')} | {c.get('source')} | "
            f"page={c.get('page')} | chunk_id={c.get('chunk_id')} | "
            f"vector_id={c.get('vector_id')}{score_text}"
        )
    return "\n".join(refs)


def make_chunk_preview(chunks: List[dict], max_chars: int = 500) -> str:
    """Short chunk-text preview for CSV. Full text is saved in JSONL."""
    previews = []
    for c in chunks:
        text = (c.get("text") or "").replace("\n", " ").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        previews.append(f"[rank={c.get('rank')}] {text}")
    return "\n\n".join(previews)


def run_evaluation():
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(PINECONE_INDEX_NAME)
    embed_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_filename = f"rag_eval_{timestamp}.csv"
    jsonl_filename = f"rag_eval_{timestamp}.jsonl"

    csv_rows = []
    jsonl_rows = []

    for question in TEST_QUESTIONS:
        try:
            retriever = build_retriever(question, embed_model, index, top_k=TOP_K)
            chain = get_llm_chain(retriever)
            result = chain.invoke(question)

            retrieved_chunks = result.get("retrieved_chunks", [])
            sources = result.get("sources", [])

            csv_rows.append({
                "question": question,
                "answer": result.get("answer", ""),
                "retrieved_sources": "; ".join(sources),
                "retrieved_chunk_refs": make_chunk_reference(retrieved_chunks),
                "retrieved_chunk_preview": make_chunk_preview(retrieved_chunks),
                # Fill these manually during human review.
                "human_retrieval_sufficient_1_to_5": "",
                "human_faithfulness_1_to_5": "",
                "human_answer_relevancy_1_to_5": "",
                "human_notes": "",
            })

            jsonl_rows.append({
                "question": question,
                "answer": result.get("answer", ""),
                "retrieved_sources": sources,
                "retrieved_chunks": retrieved_chunks,
                "human_eval_schema": {
                    "retrieval_sufficient_1_to_5": "Do the retrieved chunks contain enough information to answer the question?",
                    "faithfulness_1_to_5": "Is the answer supported by the retrieved chunks without unsupported claims?",
                    "answer_relevancy_1_to_5": "Does the answer directly address the question?",
                },
            })

            print(f"Done: {question[:70]}...")

        except Exception as e:
            print(f"Error on '{question}': {e}")
            csv_rows.append({
                "question": question,
                "answer": f"ERROR: {e}",
                "retrieved_sources": "",
                "retrieved_chunk_refs": "",
                "retrieved_chunk_preview": "",
                "human_retrieval_sufficient_1_to_5": "",
                "human_faithfulness_1_to_5": "",
                "human_answer_relevancy_1_to_5": "",
                "human_notes": "",
            })
            jsonl_rows.append({
                "question": question,
                "error": str(e),
            })

    fieldnames = [
        "question",
        "answer",
        "retrieved_sources",
        "retrieved_chunk_refs",
        "retrieved_chunk_preview",
        "human_retrieval_sufficient_1_to_5",
        "human_faithfulness_1_to_5",
        "human_answer_relevancy_1_to_5",
        "human_notes",
    ]

    with open(csv_filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    with open(jsonl_filename, "w", encoding="utf-8") as f:
        for row in jsonl_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nSaved CSV summary to {csv_filename}")
    print(f"Saved JSONL details to {jsonl_filename}")


if __name__ == "__main__":
    run_evaluation()
