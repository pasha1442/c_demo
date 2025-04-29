from typing import Any, Dict
from chat.vector_databases.base_vector_database import BaseVectorDatabase
from chat.vector_databases.qdrant import Qdrant
from chat.vector_databases.pinecone import Pinecone
from chat.vector_databases.neo4j import Neo4j
from metering.services.openmeter import OpenMeter


class VectorDB:
    def __init__(self, company=None, openmeter_obj=None) -> None:
        self.company = company
        if openmeter_obj:
            self.openmeter_obj = openmeter_obj
        else:
            self.openmeter_obj = OpenMeter(company=self.company)

    def get_vector_database(self, provider_name: str, **kwargs) -> BaseVectorDatabase:
        """
        Returns an instance of the requested vector provider.
        :param provider_name: "qdrant", "pinecone", or "neo4j" (case-insensitive).
        :param kwargs: additional arguments specific to each provider.
        """
        provider_map = {
            "qdrant": Qdrant,
            "pinecone": Pinecone,
            "neo4j": Neo4j
        }

        provider_name = provider_name.lower()

        if provider_name not in provider_map:
            raise ValueError(f"Unsupported provider: {provider_name}")

        provider_class = provider_map[provider_name]
        return provider_class(company=self.company, **kwargs)

    @staticmethod
    def get_vector_container_name(company) -> str:
        return f"{company.prefix}_{company.current_env}_{company.id}"
