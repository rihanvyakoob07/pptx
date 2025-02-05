
import asyncio
from datetime import datetime
from fastapi import UploadFile
from uuid import UUID
import pandas as pd
import numpy as np
from typing import List, Tuple, Any, Dict, Optional
from io import BytesIO
from qdrant_client.models import ScoredPoint

from app.core.logger import logger
from app.core.models import (
    Options, BaseResponseDTO, MessageType, RFxResponseDTO, 
    RFxType, DocReference, RFxSlideDeckResponseDTO
)
from app.core.utils.llm.openai_helpers import get_embeddings, get_chat_completion
from app.core.database import get_connection  # Add this line to import get_connection
from app.core.utils.qdrant_helpers import batch_search_documents, search_documents
from app.core.utils.persist_helpers import add_message, fetch_messages, upload_file, create_conversation
from app.core.utils.llm.prompts import refine_response_prompt, response_prompt, fallback_prompt
from app.core.utils.shared.constants import PERCENTILE, CUTOFF
from app.core.utils.pptx_helpers import generate_combined_slides

# Helper functions
async def get_answer(question: str, rf_type: RFxType, options: Options, 
                    conversation_id: UUID, limit: int, fallback: bool) -> Tuple[List[BaseResponseDTO], Dict]:
    em_query = await get_embeddings(question)
    rel_responses, unique_payloads = await find_relevant_docs(em_query)
    
    system_message = {
        "role": "system",
        "content": fallback_prompt(options, True) if not rel_responses else response_prompt("\n".join(rel_responses), rf_type, options, True)
    }
    messages = [system_message, {"role": "user", "content": question}]
    answers = await answer_one_question(messages, unique_payloads, limit)
    
    return answers, unique_payloads

async def new_multiple_queries(
    conversation_id: UUID,
    user_id: str, 
    rf_type: str,
    questions: List[str],
    options: Options,
    limit: int,
    fallback: bool
) -> RFxSlideDeckResponseDTO:
    try:
        # Create conversation
        async with get_connection() as conn:
            await create_conversation(
                conn=conn,
                conversation_id=conversation_id,
                title=f"Multiple Questions {conversation_id}"
            )

        answers = []
        slides_urls = []

        # Process questions
        for question in questions:
            answer_response, _ = await get_answer(
                question, rf_type, options, conversation_id, limit, fallback
            )
            
            # Save answers
            for answer in answer_response:
                await add_message(
                    msg_text=answer.text,
                    doc_references=answer.referenceLinks,
                    msg_type=MessageType.system,
                    conversation_id=conversation_id,
                    sender="assistant"
                )
                
                # Collect slide URLs if they exist
                if answer.referenceLinks:
                    for ref in answer.referenceLinks:
                        if ref.slide:
                            slides_urls.append(ref.slide)

            answers.append(RFxResponseDTO(
                conversation_id=conversation_id,
                question=question,
                results=answer_response
            ))

        # Set default slide_deck URL
        slide_deck_url = ""

        # Generate combined slides if we have any
        if slides_urls:
            try:
                slide_deck_url = await generate_combined_slides(slides_urls) or ""
            except Exception as e:
                logger.error(f"Error generating slides: {str(e)}")
                slide_deck_url = ""

        return RFxSlideDeckResponseDTO(
            slide_deck=slide_deck_url,
            answers=answers
        )

    except Exception as e:
        logger.exception(f"Error in new_multiple_queries: {str(e)}")
        # Return empty response with valid string for slide_deck
        return RFxSlideDeckResponseDTO(
            slide_deck="",
            answers=[]
        )

# Helper functions
async def find_relevant_docs(em_query: List[float]) -> Tuple[List[str], Dict[Any, Dict[str, Any]]]:
    rel_docs = await search_documents(em_query)
    rel_responses, unique_payloads = filter_docs(rel_docs, PERCENTILE)
    return rel_responses, unique_payloads

async def answer_one_question(messages: List[Dict[str, str]], unique_payloads: Dict[Any, Dict[str, Any]], n: int) -> List[BaseResponseDTO]:
    response = await get_chat_completion(messages, temperature=0.2, n=n)
    choices = response.choices
    content = [c.message.content.replace("\n", "") for c in choices]
    
    refs = [DocReference(
        id=pl["doc_id"],
        url=pl["payload"]["source"],
        label=pl["payload"]["title"],
        image_url=pl["payload"]["images"][0] if pl["payload"].get("images") else None,
        slide=pl["payload"]["slide"] if pl["payload"].get("slide") else None
    ) for pl in unique_payloads]
    
    return [BaseResponseDTO(text=c, referenceLinks=refs, sender="assistant") for c in content]

# Main functions
async def refine(conversation_id: UUID, user_id: UUID, rf_type: RFxType, question: str, 
                options: Options, limit: int, fallback: bool) -> RFxResponseDTO:
    try:
        await add_message(msg_text=question, doc_references=[], msg_type=MessageType.user,
                         conversation_id=conversation_id, file_links=None, sender="user")
        
        messages = await fetch_messages(conversation_id)
        orig_question = messages[-1]
        embedded_question = await get_embeddings(question + orig_question['text'])
        rel_responses, unique_payloads = await find_relevant_docs(embedded_question)
        
        system_message = {"role": "system", "content": refine_response_prompt(" ".join(rel_responses), rf_type, options)}
        messages = [system_message, {"role": "user", "content": question}]
        
        answers = await answer_one_question(messages, unique_payloads, limit)
        
        await asyncio.gather(*[add_message(msg_text=answer.text, doc_references=answer.referenceLinks,
                             msg_type=MessageType.system, conversation_id=conversation_id,
                             file_links=None, sender="assistant") for answer in answers])
        
        return RFxResponseDTO(conversation_id=conversation_id, question=question, results=answers)
    except Exception as e:
        logger.exception(f"Error in refine: {str(e)}")
        raise


async def new_query(conversation_id: UUID, rf_type: RFxType, question: str,
                   options: Options, limit: int, fallback: bool) -> RFxResponseDTO:
    try:
        await add_message(msg_text=question, doc_references=[], msg_type=MessageType.user,
                         conversation_id=conversation_id, file_links=None, sender="user")
        
        em_query = await get_embeddings(question)
        rel_responses, unique_payloads = await find_relevant_docs(em_query)
        
        if not rel_responses and not fallback:
            response = RFxResponseDTO(
                conversation_id=conversation_id,
                question=question,
                results=[BaseResponseDTO(
                    text="No matching information found. Enable 'Fallback' to generate response.",
                    sender="assistant",
                    referenceLinks=[]
                )]
            )
            await add_message(msg_text=response.results[0].text, doc_references=[],
                            msg_type=MessageType.system, conversation_id=conversation_id,
                            file_links=None, sender="assistant")
            return response
            
        system_message = {
            "role": "system",
            "content": fallback_prompt(options, True) if not rel_responses else response_prompt("\n".join(rel_responses), rf_type, options, True)
        }
        messages = [system_message, {"role": "user", "content": question}]
        
        answers = await answer_one_question(messages, unique_payloads, limit)
        
        await asyncio.gather(*[add_message(msg_text=answer.text, doc_references=answer.referenceLinks,
                             msg_type=MessageType.system, conversation_id=conversation_id,
                             file_links=None, sender="assistant") for answer in answers])
        
        return RFxResponseDTO(conversation_id=conversation_id, question=question, results=answers)
    except Exception as e:
        logger.exception(f"Error in new_query: {str(e)}")
        raise

async def process_file(file: UploadFile, options: Options, rf_type: RFxType, out_file: str,
                      fallback: bool, conversation_id: UUID, user_id: UUID) -> BaseResponseDTO:
    try:
        df = pd.read_csv(file.file) if file.content_type == "text/csv" else pd.read_excel(file.file)
        questions = df.iloc[:, 0].tolist()
        
        em_qs = await batch_embed(questions)
        documents = await batch_search_documents(em_qs)
        
        results = []
        for doc_set in documents:
            rel_responses, unique_payloads = filter_docs(doc_set, PERCENTILE)
            results.append((rel_responses, unique_payloads))
            
        all_answers = []
        for i, (rel_responses, unique_payloads) in enumerate(results):
            messages = [{
                "role": "system",
                "content": fallback_prompt(options, False) if not rel_responses else response_prompt("\n".join(rel_responses), rf_type, options, False)
            }, {
                "role": "user",
                "content": questions[i]
            }]
            answers = await answer_one_question(messages, unique_payloads, 1)
            all_answers.append(answers)
            
        buffer = create_file(questions, all_answers, out_file)
        out_file_name = f"{file.filename.split('.')[0]}-response-{datetime.utcnow().strftime('%d_%m_%Y-%H_%M_%S')}.{out_file}"
        url = await upload_file(buffer, out_file_name)
        
        msg_text = f"File {out_file_name} created."
        final_response = BaseResponseDTO(text=msg_text, referenceLinks=[], file_links=[url], sender="assistant")
        
        await add_message(msg_text=msg_text, doc_references=[], msg_type=MessageType.system,
                         conversation_id=conversation_id, file_links=[url], sender="assistant")
                         
        return final_response
    except Exception as e:
        logger.exception(f"Error processing file: {str(e)}")
        raise


def load_file(file: UploadFile) -> pd.DataFrame:
    """Load file content into DataFrame"""
    try:
        if file.content_type == "text/csv":
            return pd.read_csv(file.file)
        elif file.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            return pd.read_excel(file.file, engine="openpyxl")
        else:
            raise ValueError(f"Unsupported file type: {file.content_type}")
    except Exception as e:
        logger.error(f"Error loading file: {str(e)}")
        raise

async def batch_embed(questions: List[str]) -> List[List[float]]:
    """Batch embed questions using OpenAI embeddings"""
    try:
        tasks = [get_embeddings(question) for question in questions]
        return await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error in batch embedding: {str(e)}")
        raise


def create_file(questions: List[str], responses: List[List[BaseResponseDTO]], file_type: str) -> BytesIO:
    data = [
        {
            "Question": questions[i],
            "Answer": responses[i][0].text,
            "References": [responses[i][0].referenceLinks[j].url for j in range(len(responses[i][0].referenceLinks))],
            "Images": [responses[i][0].referenceLinks[j].image_url for j in range(len(responses[i][0].referenceLinks))]
        } for i in range(len(questions))
    ]
    df = pd.DataFrame(data)
    buffer = BytesIO()

    if file_type == "csv":
        df.to_csv(buffer, index=False)
    elif file_type == "xlsx":
        df.to_excel(buffer, index=False, engine="openpyxl")
        
    buffer.seek(0)
    return buffer

def __calculate_threshold(scores: List[float], p: int) -> float:
    return np.percentile(scores, p)

def filter_docs(rel_docs: List[ScoredPoint], p: int) -> Tuple[List[str], dict[Any, dict[str, Any]]]:
    scores = [doc.score for doc in rel_docs]
    threshold = __calculate_threshold(scores, p)
    if threshold < CUTOFF:
        return [], {}

    rel_payloads = [{"doc_id": doc.id, "payload": doc.payload} for doc in rel_docs if doc.score > threshold and doc.payload is not None]
    rel_responses = [pl["payload"]["answer"] for pl in rel_payloads if pl["payload"]["answer"] is not None]

    unique_payloads = {obj["payload"]["source"]: obj for obj in rel_payloads}.values()
    return rel_responses, unique_payloads

async def answer_one_question(messages: List[dict[str, str]], unique_payloads: dict[Any, dict[str, Any]], n: int) -> List[BaseResponseDTO]:
    response = await get_chat_completion(messages, temperature=0.2, n=n)
    choices = response.choices
    content = [c.message.content.replace("\n", "") for c in choices]

    refs = [
        DocReference(
            id=pl["doc_id"],
            url=pl["payload"]["source"],
            label=pl["payload"]["title"],
            image_url=pl["payload"]["images"][0] if pl['payload'].get("images") else None,
            slide=pl["payload"]["slide"] if pl["payload"].get("slide") else None,
        ) for pl in unique_payloads
    ]
    answers = [BaseResponseDTO(text=c, referenceLinks=refs, sender="assistant") for c in content]

    return answers


async def find_relevant_docs(em_query: List[float]) -> Tuple[List[str], dict[Any, dict[str, Any]]]:
    rel_docs = await search_documents(em_query)
    rel_responses, unique_payloads = filter_docs(rel_docs, PERCENTILE)
    
    return rel_responses, unique_payloads
