from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from logger import logger
from modules.csv_handlers import save_hrv_csv
from modules.db import get_db

router = APIRouter()


@router.post("/upload_csv/")
async def upload_csv(
    file: UploadFile = File(...),
    participant_code: str = Form("P001"),
    db: Session = Depends(get_db),
):
    try:
        file_bytes = await file.read()
        result = save_hrv_csv(file_bytes, participant_code, db)
        logger.info(f"CSV upload: {result}")
        return {
            "message": "CSV processed",
            "participant_code": participant_code,
            **result,
        }
    except Exception as e:
        logger.exception("CSV upload failed")
        return JSONResponse(status_code=500, content={"error": str(e)})