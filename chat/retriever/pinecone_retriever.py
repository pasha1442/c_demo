import nest_asyncio
from chat.clients.workflows.agent_state import PipelineState
from company.models import CompanySetting
from openai import OpenAI
import time
from basics.custom_exception import PineconeConnectionError, PineconeDataRetrievalError
from chat.retriever.base_retriever import BaseRetriever
from pinecone.grpc import PineconeGRPC as Pinecone
from backend.logger import Logger
nest_asyncio.apply()
# load_dotenv()




workflow_logger = Logger(Logger.WORKFLOW_LOG)


class PineconeRetriever(BaseRetriever):

    def __init__(self, data_source, state):
        try:
            start_time = time.time()
            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id

            super().__init__()
            self.database = self.DATABASE_PINECONE
            self.database_type = self.DATABASE_TYPE_Vector_DB

            self.openmeter_obj = context.openmeter

            if self.company:
                self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_VECTOR_DB_PINECONE_CREDENTIALS, company=self.company)
            else:
                self.credentials = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_VECTOR_DB_PINECONE_CREDENTIALS)
            self.data_source = data_source
            self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}

            pc = Pinecone(api_key=self.credentials_dict.get('api_key'))
            self.index = pc.Index(host=self.credentials_dict.get('host'))
            self.namespace = self.credentials_dict.get('namespace')

            self.openai_client = OpenAI()

            workflow_logger.add \
                (f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (Pinecone) -> : [{round(time.time() - start_time, 2)} sec ] Initialization complete")


        except Exception as e:
            raise PineconeConnectionError \
                (f"[{self.company.name}] ({self.session_id})- Could not connect with pinecone data source")

    def get_embedding(self, query):
        start_time = time.time()
        response = self.openai_client.embeddings.create(
            input=query,
            model="text-embedding-ada-002"
        )
        embeddings = response.data[0].embedding  # type:ignore
        workflow_logger.add \
            (f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (Pinecone) -> : [{round(time.time() - start_time, 2)} sec ] fetched embedding")
        return embeddings

    def retriever(self, query: str):

        query_embedding = self.get_embedding(query)

        start_time = time.time()
        if self.namespace:
            response = self.index.query(vector=query_embedding, top_k=5, include_metadata=True,
                                        namespace=self.namespace)

        else:
            response = self.index.query(vector=query_embedding, top_k=5, include_metadata=True)

        matches = response['matches']
        info = ''
        for match in matches:
            data = match['metadata']
            for key, value in data.items():
                info += key + ' : '
                info += value + ' '

        workflow_logger.add \
            (f"Knowledge-Retriever [{self.company}]  ({self.session_id}) -> (Pinecone) -> : [{round(time.time() - start_time, 2)} sec ] final response from pinecone - {info}")
        return info

    def query(self, query: str) -> str:
        try:
            _res = self.retriever(query)
            self.push_knowledge_retriever_data_to_openmeter()
            print(_res)
            return _res

        except Exception as e:
            raise PineconeDataRetrievalError \
                (f"[{self.company.name}]  ({self.session_id})- Could not retrieve data from pinecone data source")
            return None
