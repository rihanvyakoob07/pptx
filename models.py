from enum import Enum
from uuid import UUID
from pydantic import BaseModel, field_validator
from typing import List, Optional, Union
from datetime import datetime
from app.core.utils.shared.constants import DEFAULT_CONFIG
class RFxType(Enum):
    proposal = "proposal"
    comment = "comment"

class Document(BaseModel):
    text: str
    metadata: dict

class TranslateResult(BaseModel):
    original_content: str
    translated_content: str


class Options(BaseModel):
    length: Optional[str] = DEFAULT_CONFIG
    tone: Optional[str] = DEFAULT_CONFIG

class MultipleQuestionsRequest(BaseModel):
    questions: List[str]
    length: Optional[str] = "medium"
    tone: Optional[str] = "professional"

    @field_validator('questions')
    def validate_questions(cls, v):
        if not v:
            raise ValueError('questions list cannot be empty')
        if not all(isinstance(q, str) for q in v):
            raise ValueError('all questions must be strings')
        if not all(q.strip() for q in v):
            raise ValueError('questions cannot be empty strings')
        return v
class PresentationPreferences(BaseModel):
    theme_color: Optional[str]
    include_section_headers: Optional[bool] = True
    slide_transition: Optional[str]
class DocReference(BaseModel):
    id: UUID
    label: str
    url: str
    image_url: Optional[str] = None
    slide: Optional[str] = None

class BaseResponseDTO(BaseModel):
    text: str
    sender: str
    referenceLinks: Optional[List[DocReference]] = None
    file_links: Optional[List[str]] = None
    
class RFxResponseDTO(BaseModel):
    conversation_id: UUID
    timestamp: Optional[datetime] = datetime.utcnow()
    results: List[BaseResponseDTO]

class RFxSlideDeckResponseDTO(BaseModel):
    slide_deck:str
    answers : List[RFxResponseDTO]


class TranslateResponse(BaseModel):
    results: List[TranslateResult]

class MessageType(Enum):
    user = "USER"
    system = "AI"



class DocReference(BaseModel):
    id: UUID
    label: str
    url: str
    image_url: Optional[str] = None
    slide: Optional[str] = None

class BaseResponseDTO(BaseModel):
    text: str
    sender: str
    referenceLinks: Optional[List[DocReference]] = None
    file_links: Optional[List[str]] = None
    
class RFxResponseDTO(BaseModel):
    conversation_id: UUID
    timestamp: Optional[datetime] = datetime.utcnow()
    results: List[BaseResponseDTO]

class RFxSlideDeckResponseDTO(BaseModel):
    slide_deck: str  # URL to the combined slide deck
    answers: List[RFxResponseDTO]
class Options(BaseModel):
    length: Optional[str] = DEFAULT_CONFIG
    tone: Optional[str] = DEFAULT_CONFIG

class MultipleQuestions(BaseModel):
    questions: List[str]  # Only require questions list
    length: Optional[str] = DEFAULT_CONFIG
    tone: Optional[str] = DEFAULT_CONFIG

class GPTModelInfo(BaseModel):
    name: str
    input_rate: float
    output_rate: float
    max_token: int
    encoding: str
    is_azure: Optional[bool] = False

class RFxRequest(BaseModel):
    options: Options

class ConversationsDTO(BaseModel):
    id: UUID
    user_id: str
    created_on: datetime
    title: Optional[str] = None
    summary: Optional[str] = None

class TranslatedFileResponse(BaseModel):  # Added TranslatedFileResponse class
    result: str  # Path or URL to the saved translated file
]
