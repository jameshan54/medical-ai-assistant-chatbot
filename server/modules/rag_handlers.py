import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone

from modules.llm import format_docs

load_dotenv()


def _query_pinecone(query: str, top_k: int = 3) -> list[Document]:
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index = pc.Index(os.environ["PINECONE_INDEX_NAME"])
    embed_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    embedded_query = embed_model.embed_query(query)
    res = index.query(vector=embedded_query, top_k=top_k, include_metadata=True)

    return [
        Document(
            page_content=match["metadata"].get("text", ""),
            metadata=match["metadata"],
        )
        for match in res["matches"]
    ]


def search_research_docs(
    query: str, top_k: int = 3
) -> tuple[str, list[str], list[dict]]:
    docs = _query_pinecone(query, top_k=top_k)
    context = format_docs(docs)
    sources = sorted(set(d.metadata.get("source", "unknown") for d in docs))
    chunks = [
        {
            "text": d.page_content,
            "source": d.metadata.get("source", "unknown"),
        }
        for d in docs
    ]
    return context, sources, chunks
