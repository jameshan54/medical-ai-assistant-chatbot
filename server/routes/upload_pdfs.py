# PDF 받기 → pdf_handlers.py로 저장 요청 → load_vectorstore.py로 Pinecone 저장 요청

from fastapi import APIRouter, UploadFile, File
from typing import List
from modules.pdf_handlers import save_uploaded_files
from modules.load_vectorstore import load_vectorstore
from fastapi.responses import JSONResponse
from logger import logger


router=APIRouter()

@router.post("/upload_pdfs/")
async def upload_pdfs(files:List[UploadFile] = File(...)):
    try:
        logger.info("Recieved uploaded files")

        # 1. Save PDFs to server local folder
        file_paths=save_uploaded_files(files)

        # 2. Load saved PDFs into Pinecone
        load_vectorstore(file_paths)

        logger.info("Document added to vectorstore")

        return {"messages":"Files processed and vectorstore updated",
                "saved_files":file_paths}
    
    except Exception as e:
        logger.exception("Error during PDF upload")
        return JSONResponse(status_code=500,content={"error":str(e)})