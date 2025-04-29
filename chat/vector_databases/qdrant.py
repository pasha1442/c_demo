from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Distance,
    VectorParams
)
from chat.vector_databases.base_vector_database import BaseVectorDatabase
from company.models import CompanySetting
from chat.constants import DEFAULT_QDRANT_HOST, DEFAULT_QDRANT_PORT




class Qdrant(BaseVectorDatabase):
    DEFAULT_VECTOR_SIZE = 1536

    def __init__(self, company, host=None, port=None):
        self.company = company
        self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_VECTOR_DB_QDRANT_CREDENTIALS, company=self.company)

        if not host:
            host = self.credentials.get("host", DEFAULT_QDRANT_HOST)
        if not port:
            port = self.credentials.get("port", DEFAULT_QDRANT_PORT)

        self.client = QdrantClient(host=host, port=port)

    def _ensure_collection_exists(
        self, 
        collection_name: str, 
        extra_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Helper to create the Qdrant collection if it doesn't exist.
        """
        if extra_params is None:
            extra_params = {}

        vector_size = extra_params.get("vector_size", self.DEFAULT_VECTOR_SIZE)

        try:
            self.client.get_collection(collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )

    def push(
        self,
        container_name: str,
        vectors: List[List[float]],
        ids: List[Any],
        metadata: List[Dict[str, Any]],
        extra_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
            container name : collection name
        """
        self._ensure_collection_exists(container_name, extra_params)

        points = []
        for i, vec in enumerate(vectors):
            point = PointStruct(
                id=ids[i],
                vector=vec,
                payload=metadata[i] if metadata else {}
            )
            points.append(point)

        self.client.upsert(collection_name=container_name, points=points)

    def query(
        self,
        container_name: str,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        extra_params: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
            container name : collection name
        """
        query_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = Filter(must=conditions)

        from chat.utils import create_embedding
        query_embedding = create_embedding(query)
        results = self.client.search(
            collection_name=container_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=query_filter
        )
        return results
