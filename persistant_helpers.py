#persist_helpers.py
import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from asyncpg import Record
from contextlib import _AsyncGeneratorContextManager
from io import BytesIO

from app.core.database import get_connection, blob_service_client
from app.core.models import DocReference, MessageType
from app.core.logger import logger

async def fetch_messages(conversation_id: UUID) -> List[Record]:
    """
    Fetch messages from the database for a given conversation ID.
    """
    async with get_connection() as conn:
        logger.info(f"Fetching messages with conversation ID {conversation_id}")
        try:
            query = 'SELECT * FROM messages WHERE conversation_id = $1;'
            messages = await conn.fetch(query, conversation_id)
            logger.info(f"Fetched {len(messages)} messages for conversation {conversation_id}")
            return messages
        except Exception as e:
            logger.error(f"Error fetching messages: {str(e)}")
            raise

async def fetch_messages_with_refs(conversation_id: UUID) -> List[Record]:
    """
    Fetch messages and their associated reference links for a given conversation ID.
    """
    async with get_connection() as conn:
        try:
            query = '''
            SELECT M.id, M.text, M.file_links, M.conversation_id,
                   M.msg_type, M.timestamp, M.sender,
                   RL.label, RL.url, RL.image_url, RL.slide, 
                   RL.id AS ref_id
            FROM messages M
            LEFT JOIN reference_links RL ON M.id = RL.message_id
            WHERE M.conversation_id = $1 
            ORDER BY M.timestamp ASC;
            '''
            return await conn.fetch(query, conversation_id)
        except Exception as e:
            logger.exception(f"Error fetching messages with refs: {str(e)}")
            raise

async def add_message(
    msg_text: str,
    doc_references: List[DocReference],
    msg_type: MessageType,
    conversation_id: UUID,
    file_links: Optional[List[str]] = None,
    sender: str = "user"
) -> UUID:
    """
    Insert a new message into the database, attaching any provided file links and references.
    """
    async with get_connection() as conn:
        try:
            message_id = uuid4()
            await conn.execute(
                """
                INSERT INTO messages (id, text, conversation_id, msg_type, 
                                      file_links, sender, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                message_id,
                msg_text,
                conversation_id,
                msg_type.value,
                file_links or [],
                sender,
                datetime.now()
            )

            for doc_ref in doc_references:
                await conn.execute(
                    '''
                    INSERT INTO reference_links(id, doc_id, label, url,
                                                image_url, message_id, slide)
                    VALUES($1, $2, $3, $4, $5, $6, $7);
                    ''',
                    uuid4(),
                    doc_ref.id,
                    doc_ref.label,
                    doc_ref.url,
                    doc_ref.image_url,
                    message_id,
                    doc_ref.slide
                )
            
            logger.info(f"Added message {message_id} to conversation {conversation_id}")
            return message_id
        except Exception as e:
            logger.error(f"Error adding message: {str(e)}")
            raise

async def fetch_all_conversations() -> List[Record]:
    """
    Retrieve all conversations from the database in descending order of creation date.
    """
    async with get_connection() as conn:
        try:
            query = 'SELECT * FROM conversations ORDER BY created_on DESC;'
            conversations = await conn.fetch(query)
            logger.info(f"Fetched {len(conversations)} conversations")
            return conversations
        except Exception as e:
            logger.error(f"Error fetching conversations: {str(e)}")
            raise

async def create_conversation(
    conn: _AsyncGeneratorContextManager,
    conversation_id: UUID,
    title: str
) -> None:
    """
    Create a new conversation record in the database.
    """
    try:
        await conn.execute(
            '''
            INSERT INTO conversations(id, created_on, title)
            VALUES($1, $2, $3);
            ''',
            conversation_id,
            datetime.now(),
            title
        )
        logger.info(f"Created conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise

async def upload_file(file: BytesIO, file_name: str) -> str:
    """
    Upload a file to Azure Blob Storage and return the file URL.
    """
    try:
        account_name = os.getenv("STORAGE_ACCOUNT_NAME")
        container_name = os.getenv("STORAGE_CONTAINER_NAME")
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=file_name)
        await blob_client.upload_blob(file)
        url = f"https://{account_name}.blob.core.windows.net/{container_name}/{file_name}"
        return url
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise
