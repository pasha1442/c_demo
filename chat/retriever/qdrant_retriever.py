import nest_asyncio
from backend.services.qdrant_service import QdrantService
from chat import utils
import logging
from basics.custom_exception import QdrantConnectionError, QdrantDataRetrievalError
from chat.clients.workflows.agent_state import PipelineState
from chat.retriever.base_retriever import BaseRetriever
nest_asyncio.apply()

logger = logging.getLogger("workflow_log")


class QdrantRetriever(BaseRetriever):

    def __init__(self, data_source, state):
        try:
            super().__init__()
            self.database = self.DATABASE_QDRANT
            self.database_type = self.DATABASE_TYPE_Vector_DB
            self.data_source = data_source

            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id
            self.openmeter_obj = context.openmeter
            self.client_identifier = context.extra_save_data["client_identifier"]

            self.qdrant_service = QdrantService()
            self.collection_name = self.qdrant_service.get_collection_name_for_company(self.company)
        except Exception as e:
            raise QdrantConnectionError (f"[{self.company.name}] ({self.session_id})- Could not connect with pinecone data source {e}")

    def retriever(self, query: str):
        query_embedding = utils.create_embedding(query)
        collection_name = self.collection_name
        filter_criteria = {
            'client_identifier' : self.client_identifier
        }
        search_results = self.qdrant_service.search(collection_name=collection_name, query_vector=query_embedding, limit=5, filter_criteria=filter_criteria)
        memories = [result.payload.get("memory", "") for result in search_results]
        final_result = "Related memories of current customer: " + " ".join(memories)

        return final_result

    def query(self, query: str) -> str:
        try:
            _res = self.retriever(query)
            self.push_knowledge_retriever_data_to_openmeter()
            print(_res)
            return _res

        except Exception as e:
            raise QdrantDataRetrievalError (f"[{self.company.name}]  ({self.session_id})- Could not retrieve data from pinecone data source")
