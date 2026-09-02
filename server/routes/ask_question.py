from fastapi import APIRouter, Form, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from modules.db import get_db
from modules.hrv_agent import run_hrv_agent
from logger import logger

router = APIRouter()


@router.post("/ask/")
async def ask_question(
    question: str = Form(...),
    participant_code: str = Form("P001"),
    db: Session = Depends(get_db),
):
    try:
        logger.info(f"user query: {question} (participant={participant_code})")

        result = run_hrv_agent(
            question,
            db,
            participant_code,
            run_name="ask",
            ls_tags=["ask"],
            ls_metadata={"participant_code": participant_code},
        )

        logger.info(f"query successful (tools_used={result.get('tools_used', [])})")
        return result

    except Exception as e:
        logger.exception("Error processing question")
        return JSONResponse(status_code=500, content={"error": str(e)})