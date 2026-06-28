from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def format_docs(docs):
    """Join retrieved chunks into a single context string for the prompt."""
    formatted = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata or {}
        source = meta.get("source", "unknown")
        page = meta.get("page_number", meta.get("page", "unknown"))
        chunk_id = meta.get("chunk_id", "unknown")

        formatted.append(
            f"[Chunk {i} | source={source} | page={page} | chunk_id={chunk_id}]\n"
            f"{d.page_content}"
        )

    return "\n\n".join(formatted)


def serialize_retrieved_chunks(docs):
    """Return retrieved chunk metadata + text for evaluation/debugging."""
    chunks = []

    for rank, d in enumerate(docs, start=1):
        meta = d.metadata or {}
        chunks.append({
            "rank": rank,
            "source": meta.get("source", "unknown"),
            "page": meta.get("page_number", meta.get("page", "unknown")),
            "page_index": meta.get("page", None),
            "chunk_id": meta.get("chunk_id", "unknown"),
            "vector_id": meta.get("vector_id", "unknown"),
            "score": meta.get("score", None),
            "text": d.page_content,
        })

    return chunks


def get_llm_chain(retriever, sql_context: str = ""):
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile"
    )

    prompt = PromptTemplate(
        input_variables=["context", "question", "sql_context"],
        template="""
        [system prompt]
        ## Role
        You are an HRV Research Assistant helping participants
        in a health study understand their Heart Rate Variability
        (HRV) data in simple, everyday language.

        ## Behavioral rules
        - Always explain HRV concepts without medical jargon
        - Frame HRV changes as "patterns worth noticing",
          never as alarms or diagnoses
        - Be warm, encouraging, and supportive in tone
        - Ground answers in the personal HRV data and/or
          research context sections below. Do not use outside knowledge.
        - Never invent personal numbers. Use only numbers from
          the personal HRV data section when provided.
        - Never speculate or invent claims not supported by the context below.

        ## Output format
        - Simple yes/no or definition questions: under 80 words
        - "How does X work" questions: under 150 words
        - First-time concept explanation (e.g., "What is HRV?"):
          under 200 words, use an analogy
        - Always end with ONE practical tip (not counted in limit)
        - Write at 6th grade reading level

        ## Fallback rules
        - If you truly cannot answer from the context below: say
          "That's a great question — please bring it up with your
          research coordinator!"
        - If the question is unrelated to HRV: say "I'm set
          up to help specifically with HRV and this study."

        ## Safety rules
        - Never diagnose, prescribe, or make clinical claims
        - Never use the words "dangerous" or "alarming"
          about a participant's HRV
        - Never recommend stopping medication or treatment
        - If a participant seems distressed, encourage them
          to speak with their researcher or doctor

        ## Personal HRV data (from study database)
        {sql_context}

        ## Research context (from uploaded papers)
        {context}

        ## Context usage rules
        - When personal data is provided, you may reference specific numbers from it.
        - When only research context is provided, do not invent personal numbers.
        - For hybrid questions, connect personal patterns to research findings cautiously.
        - If personal data says "Not applicable" or "no readings", ignore it for that question.

        🙋 **User Question**:
        {question}

        💬 **Answer**:
        """
    )

    # Keep retrieved Document objects alongside the question so evaluation code
    # can inspect source/page/chunk_id/score/text without running retrieval again.
    retrieve_with_sources = RunnableLambda(
        lambda question: {
            "docs": retriever.invoke(question),
            "question": question,
        }
    )

    chain = (
        retrieve_with_sources
        | RunnablePassthrough.assign(
            context=lambda x: format_docs(x["docs"]),
            sql_context=lambda x: sql_context or "No personal HRV data provided.",
        )
        | {
            "answer": prompt | llm | StrOutputParser(),
            "sources": lambda x: sorted(set(
                d.metadata.get("source", "unknown") for d in x["docs"]
            )),
            "retrieved_chunks": lambda x: serialize_retrieved_chunks(x["docs"]),
        }
    )

    return chain
