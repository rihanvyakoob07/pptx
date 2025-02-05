
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










@router.post("/multiple-questions", operation_id="generate_multiple_questions")
async def generate_multiple_questions(
    body: MultipleQuestions,
    limit: Optional[int] = 3,
    fallback: Optional[bool] = False,
) -> RFxSlideDeckResponseDTO:
    try:
        # Sanitize questions
        questions_copy = [sanitize_input(q) for q in body.questions]
        
        # Configure options
        options = Options(
            length=sanitize_input(body.length) if body.length else service.default_options_config,
            tone=sanitize_input(body.tone) if body.tone else service.default_options_config
        )
        
        # Generate IDs
        conversation_id = uuid4()
        mock_user_id = str(uuid4())  # Temporary user ID for testing
        
        # Get response from service
        response = await service.generate_multiple_response(
            conversation_id=conversation_id,
            user_id=mock_user_id,
            questions=questions_copy,
            options=options,
            limit=limit,
            fallback=fallback
        )
        
        return response
        
    except Exception as e:
        logger.exception(f"Error in multiple questions generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
