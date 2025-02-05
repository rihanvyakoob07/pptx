
# routes.py
import os
import uuid
from fastapi.responses import FileResponse,JSONResponse
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status,Body, Query, Form
from typing import Optional, List
from fastapi_microsoft_identity import requires_auth
from app.core.models import RFxResponseDTO, Options, ConversationsDTO
from app.core.security import DecodedToken, get_user_ad, sanitize_input
from app.core.logger import logger
from app.core.utils.new.process_file import get_document_from_file
from app.core.utils.new.translate import get_translate_results
from app.core.utils.new.document.chatbot import chat_with_document
from app.api.v2.service import RFXService
from app.core.utils.new.save_as_file import save_translated_file
from pathlib import Path
from app.core.models import RFxResponseDTO, Options, ConversationsDTO, RFxSlideDeckResponseDTO, MultipleQuestions

router = APIRouter(prefix="/v2")
service = RFXService()










@router.post("/chatbot")
async def generate_chatbot_response(
    question: str = Body(...),
    pdf_file: UploadFile = File(None)
):
    try:
        if pdf_file:
            temp_filename = f"temp_{uuid.uuid4()}.pdf"
            with open(temp_filename, "wb") as f:
                f.write(pdf_file.file.read())
            response = chat_with_document(question, pdf_path=temp_filename)
            os.remove(temp_filename)
        else:
            response = chat_with_document(question)
        return JSONResponse(status_code=200, content=response)
    except Exception as e:
        logger.exception(f"Error in chatbot conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
