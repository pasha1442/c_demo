from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from qdrant_client.models import Distance, VectorParams
from qdrant_client.models import Filter, FieldCondition, MatchValue
from chat.constants import DEFAULT_QDRANT_HOST, DEFAULT_QDRANT_PORT

from company.models import CompanySetting



class QdrantService:
    DEFAULT_VECTOR_SIZE = 1536

    def __init__(self, company, host=None, port=None):
        self.company = company
        self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_VECTOR_DB_QDRANT_CREDENTIALS, company=self.company)

        if not host:
            host = self.credentials.get("host", DEFAULT_QDRANT_HOST)
        if not port:
            port = self.credentials.get("port", DEFAULT_QDRANT_PORT)

        self.client = QdrantClient(host=host, port=port)

    def create_collection(self, collection_name, vector_size):
        """Create a Qdrant collection."""
        vector_size = vector_size or self.DEFAULT_VECTOR_SIZE

        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        except Exception as e:
            print(f"\nException occured when creating a coolection : {e}\n")

    def get_collection(self, collection_name):
        """Retrieve collection information."""
        try:
            return self.client.get_collection(collection_name)
        except Exception as e:
            return f"Collection {collection_name} does not exist. Error: {e}"
    
    def add_vectors(self, collection_name, vectors, ids, metadata=None, vector_size=None):
        """
        Add one or multiple vectors to the collection.
        Automatically creates the collection if it doesn't exist.

        :param collection_name: name of the collection.
        :param vectors: a single vector (list of floats) or list of vectors (list of list of floats).
        :param ids: a single id (int/str) or list of ids (int/str).
        :param metadata: optional single metadata dict or list of metadata dicts.
        :param vector_size: optional vector dimension; creates collection if not present.
        """
        vector_size = vector_size or self.DEFAULT_VECTOR_SIZE

        try:
            self.client.get_collection(collection_name)
        except Exception:
            self.create_collection(collection_name, vector_size)

        is_single_vector = False
        if isinstance(vectors, (list, tuple)) and len(vectors) > 0:
            if all(isinstance(x, (float, int)) for x in vectors):
                is_single_vector = True

        if is_single_vector:
            vectors = [vectors]
            if isinstance(ids, (int, str)):
                ids = [ids]
            else:
                raise ValueError("For a single vector, 'ids' must be an int or str.")
            if metadata is not None:
                if isinstance(metadata, dict):
                    metadata = [metadata]
                else:
                    raise ValueError("For a single vector, 'metadata' must be a dict (or None).")
            else:
                metadata = [None]
        else:
            if not isinstance(vectors, list):
                raise ValueError("'vectors' must be a list of vectors.")
            if not isinstance(ids, list):
                raise ValueError("For multiple vectors, 'ids' must be a list.")
            if metadata is not None:
                if not isinstance(metadata, list) or len(metadata) != len(vectors):
                    raise ValueError(
                        "When adding multiple vectors, 'metadata' must be a list of dicts "
                        "with the same length as 'vectors', or None."
                    )
            else:
                metadata = [None] * len(vectors)

        points = []
        for i, (vid, vec) in enumerate(zip(ids, vectors)):
            points.append(
                PointStruct(
                    id=vid,
                    vector=vec,
                    payload=metadata[i] if metadata else None
                )
            )

        try:
            self.client.upsert(collection_name=collection_name, points=points)
        except Exception as e:
            print(f"\nException occurred during upsert: {e}\n")


    def search(self, collection_name, query_vector, limit=5, filter_criteria=None):
        """
        Search for similar vectors.
        collection_name : Name of the collection to search in
        query_vector : Embedded vector
        limit : result limit
        filter_criteria : 
            Given a dictionary { key: value, ... },
            return a Qdrant Filter that matches all of them exactly.
            For eg : {client_identifier : cmp_id_xxxxxx} will return vectors of
            the provided client identifier only
        """
        query_filter = None
        if filter_criteria:
            # Convert dict into must-match conditions
            conditions = [
                FieldCondition(
                    key=k,
                    match=MatchValue(value=v)
                ) for k, v in filter_criteria.items()
            ]
            query_filter = Filter(must=conditions)
        
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter
        )
        return results
    
    def get_collection_name_for_company(self, company):
        return f"{company.prefix}_{company.current_env}_{company.id}"
