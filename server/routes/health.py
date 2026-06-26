from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from logger import logger
from modules.db import engine

router = APIRouter()

EXPECTED_TABLES = ["participants", "hrv_readings"]


@router.get("/health/db")
async def health_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        tables = inspect(engine).get_table_names()
        missing = [name for name in EXPECTED_TABLES if name not in tables]

        if missing:
            logger.warning(f"Missing DB tables: {missing}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "tables": tables,
                    "missing_tables": missing,
                },
            )

        logger.info("DB health check passed")
        return {"status": "ok", "tables": tables}

    except Exception as e:
        logger.exception("DB health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "error": str(e)},
        )
