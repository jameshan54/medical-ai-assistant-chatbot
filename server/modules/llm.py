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
    return "\n\n".join(d.page_content for d in docs)


def get_llm_chain(retriever):
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile"
    )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
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
        - Ground your answer strictly in the retrieved
          research context below. Do not use outside knowledge.
        - Never speculate or invent specific numbers or claims

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

        🔍 **Context**:
        {context}

        🙋 **User Question**:
        {question}

        💬 **Answer**:
        """
    )

    # Keep retrieved Document objects (with .metadata['source']) alongside
    # the question, so callers can inspect sources without re-querying.
    retrieve_with_sources = RunnableLambda(
        lambda question: {
            "docs": retriever.invoke(question),
            "question": question,
        }
    )

    chain = (
        retrieve_with_sources
        | RunnablePassthrough.assign(
            context=lambda x: format_docs(x["docs"])
          )
        | {
            "answer": prompt | llm | StrOutputParser(),
            "sources": lambda x: sorted(set(
                d.metadata.get("source", "unknown") for d in x["docs"]
            )),
        }
    )

    return chain