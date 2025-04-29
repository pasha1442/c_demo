from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseVectorDatabase(ABC):
    """
    An abstract provider interface for vector storages.
    Each provider (Qdrant, Pinecone, Neo4j, etc.) must implement
    the 'push' and 'get' methods. 'container_name' is a generic term
    that might map to 'collection' in Qdrant, 'index' in Pinecone, etc.
    """

    AGENT = None
    database = None
    database_type = None
    openmeter_obj = None
    
    def push_knowledge_retriever_data_to_openmeter(self):
        """
        Push knowledge retriever data to OpenMeter for tracking.
        Uses the agent, database, and database_type properties.
        """
        _args = {"agent": self.AGENT, "database": self.database, "database_type": self.database_type}
        self.openmeter_obj.ingest_vector_db_call(_args)

    @abstractmethod
    def push(
        self,
        container_name: Optional[str],
        vectors: List[List[float]],
        ids: List[Any],
        metadata: List[Dict[str, Any]],
        extra_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Insert vectors into the vector storage.
        If container_name is not provided or doesn't exist,
        the provider should auto-create it.
        
        :param container_name: name of the container (collection, index, graph, etc.)
        :param vectors: list of list-of-floats (each vector)
        :param ids: list of IDs (must match length of 'vectors')
        :param metadata: list of dicts (same length as 'vectors'), for per-vector metadata
        :param extra_params: provider-specific options (e.g. vector_size, namespace, etc.)
        """
        pass

    @abstractmethod
    def query(
        self,
        container_name: str = None,
        query: str = "",
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        extra_params: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Retrieve or search for vectors based on similarity to 'query_vector'.
        Provider should return a list of results (format may vary).
        
        :param container_name: name of the container to search in
        :param query: the query to match
        :param limit: max number of results
        :param filters: optional dict of filtering criteria
        :param extra_params: provider-specific options
        :return: list of matching results
        """
        pass
