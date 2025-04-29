class BaseRetriever:

    def __init__(self):
        self.DATABASE_TYPE_GRAPH_DB = "Graph-DB"
        self.DATABASE_TYPE_Vector_DB = "Vector-DB"
        self.DATABASE_NEO4J = "Neo4j"
        self.DATABASE_PINECONE = "Pinecone"
        self.DATABASE_QDRANT = "Qdrant"
        self.AGENT = "Knowledge-Retriever"

        from chat.retriever.qdrant_retriever import QdrantRetriever
        from chat.retriever.pinecone_retriever import PineconeRetriever
        from chat.vector_databases.neo4j import Neo4j
        from chat.retriever.sql_retriever import BigQueryRetriever


        self.retriever_map = {
            "qdrant": QdrantRetriever,
            "pinecone": PineconeRetriever,
            "neo4j" : Neo4j,
            "big_query" : BigQueryRetriever
        }

    def push_knowledge_retriever_data_to_openmeter(self):
        _args = {"agent": self.AGENT, "database": self.database, "database_type": self.database_type}
        self.openmeter_obj.ingest_vector_db_call(_args)

    def get_retriever(self, data_source: str, state: dict):
        """
        Return an instance of the correct retriever class
        based on the data_source string.
        """

        retriever_cls = self.retriever_map.get(data_source.lower())
        if retriever_cls is None:
            raise ValueError(f"Unsupported data source: {data_source}")

        return retriever_cls(data_source, state)