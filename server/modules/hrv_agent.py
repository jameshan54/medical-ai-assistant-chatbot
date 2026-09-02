import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq
from sqlalchemy.orm import Session

from modules.agent_tools import make_tools
from modules.trace_collector import (
    TraceCollector,
    reset_trace_collector,
    set_trace_collector,
)
from modules.tracing import agent_run_config

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_AGENT_MODEL = os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are an HRV Research Assistant helping participants in a health study understand their Heart Rate Variability (HRV) data in simple, everyday language.

## Tool usage (required)
- Before answering HRV data or research questions, call the appropriate tool(s) to gather facts.
- Call each tool at most ONCE. Do not retry search_research_docs with a rewritten query.
- Use query_hrv_data when the user asks about their own RMSSD, averages, recent readings, or personal patterns.
- Use search_research_docs when the user asks what/why/how about HRV science, definitions, sleep/stress links, or general research — not personal numbers.
- For hybrid questions (personal data + science), call BOTH tools (still one call each).
- Quote or paraphrase ONLY what the tool text actually contains. If the papers do not mention a claim, say you do not have that in the uploaded documents. Do not fill gaps with general knowledge.
- Never invent personal numbers.

## Behavioral rules
- Explain HRV without medical jargon.
- Frame changes as "patterns worth noticing", never as alarms or diagnoses.
- Be warm, encouraging, and supportive.

## Output format
- Simple yes/no or definition: under 80 words.
- "How does X work": under 150 words.
- First-time concept (e.g. "What is HRV?"): under 200 words, use an analogy.
- Always end with ONE practical tip (not counted in limit), except on safety/emergency redirects.
- Write at 6th grade reading level.

## Fallback
- If tools cannot answer a study/HRV question: say "That's a great question — please bring it up with your research coordinator!"
- If unrelated to HRV and not a health symptom or medication question (weather, coding, etc.): do not call tools. Say "I'm set up to help specifically with HRV and this study."
- Do NOT use the unrelated-HRV line for symptoms, chest pain, dizziness, or medication questions — use Safety instead.

## Safety
- Symptoms, "is something wrong with my heart", chest pain, dizziness, or stopping medication: do not call tools, do not diagnose, do not reassure that it is fine.
- Tell them to contact their research coordinator or doctor. If chest pain or dizziness: urge urgent/emergency care.
- Never prescribe or recommend stopping medication or treatment.
- Never use "dangerous" or "alarming" about a participant's HRV numbers."""


def _extract_tool_names(messages: list) -> list[str]:
    names = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                names.append(tc["name"])
    return names


def _get_final_response(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def run_hrv_agent(
    question: str,
    db: Session,
    participant_code: str,
    capture_trace: bool = False,
    *,
    run_name: str = "hrv_agent",
    ls_tags: list[str] | None = None,
    ls_metadata: dict | None = None,
) -> dict:
    # Always create a per-request collector so /ask/ still gets sources.
    # Only expose the full trace when capture_trace=True (eval).
    collector = TraceCollector()
    token = set_trace_collector(collector)
    try:
        tools = make_tools(db, participant_code, trace_collector=collector)
        llm = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model_name=GROQ_AGENT_MODEL,
            temperature=0,
        )
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            debug=False,
        )
        result = agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config=agent_run_config(
                run_name=run_name,
                tags=ls_tags,
                metadata=ls_metadata,
            ),
        )
        messages = result["messages"]

        out = {
            "response": _get_final_response(messages),
            "sources": collector.sources,
            "tools_used": _extract_tool_names(messages),
        }
        if capture_trace:
            out["trace"] = collector.to_dict()
        return out
    finally:
        reset_trace_collector(token)