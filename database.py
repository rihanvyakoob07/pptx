import os
from qdrant_client import AsyncQdrantClient
from azure.storage.blob.aio import BlobServiceClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import asyncpg
from contextlib import asynccontextmanager

from app.core.logger import logger

qdrant_client = AsyncQdrantClient(
    url=os.getenv("QDRANT_CLOUD_URL"), 
    api_key=os.getenv("QDRANT_API_KEY"),
)

### SQL Related

connection_url = os.getenv("DATABASE_URL")
engine = create_engine(connection_url, echo=True)
Session = sessionmaker(engine)

pool = None 

async def create_pool():
    global pool
    pool = await asyncpg.create_pool(dsn=connection_url)

async def close_pool():
    await pool.close()

@asynccontextmanager
async def get_connection():
    async with pool.acquire() as connection:
        async with connection.transaction():
            try:
                yield connection
            except Exception as e:
                logger.exception(e)
                await connection.rollback()
                raise

account_name = os.getenv("STORAGE_ACCOUNT_NAME")
account_key = os.getenv("STORAGE_ACCOUNT_KEY")
AZURE_STORAGE_CONNECTION_STRING = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)