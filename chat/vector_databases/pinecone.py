from typing import Any, Dict, List, Optional
from chat.vector_databases.base_vector_database import BaseVectorDatabase


class Pinecone(BaseVectorDatabase):
    
    def __init__(self, api_key: str, environment: str, default_vector_size: int = 1536):
        pass

    def _ensure_index_exists(self, index_name: str, extra_params: Optional[Dict[str, Any]] = None) -> None:
        pass

    def push(
        self,
        container_name: Optional[str],
        vectors: List[List[float]],
        ids: List[Any],
        metadata: List[Dict[str, Any]],
        extra_params: Optional[Dict[str, Any]] = None
    ) -> None:
        pass

    def query(
        self,
        container_name: str,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        extra_params: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        pass
