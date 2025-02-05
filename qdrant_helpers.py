#qdrant_helpers.py
from typing import List
from qdrant_client.models import Record, SearchRequest, ScoredPoint
import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

from app.core.database import qdrant_client

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")

async def get_documents_by_ids(list_of_ids: List[str]) -> List[Record]:
    try:
        search_results = await qdrant_client.retrieve(
            collection_name=QDRANT_COLLECTION_NAME,
            ids=list_of_ids
        )

        return search_results
    except Exception as e:
        return {
            "message": f"Encountered error: {str(e)}"
        }


@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
async def search_documents(em_query: List[float], limit: int = 5) -> List[ScoredPoint]:
    res = await qdrant_client.search(
        collection_name=QDRANT_COLLECTION_NAME,
        query_vector=em_query,
        limit=limit
    )

    return res

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
async def batch_search_documents(em_queries: List[List[float]], limit: int = 3) -> List[List[ScoredPoint]]:
    queries = [SearchRequest(vector=query, limit=limit, with_payload=True) for query in em_queries]
    res = await qdrant_client.search_batch(
        collection_name=QDRANT_COLLECTION_NAME,
        requests=queries,
    )
    
    return res
