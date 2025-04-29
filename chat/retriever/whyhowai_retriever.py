# from llama_index.core import Document, PropertyGraphIndex
# from llama_index.core.indices.property_graph import (
#     SimpleLLMPathExtractor,
#     SchemaLLMPathExtractor,
#     DynamicLLMPathExtractor,
# )
# from llama_index.llms.openai import OpenAI
from dotenv import load_dotenv
from chat.clients.workflows.agent_state import PipelineState
from company.models import CompanySetting
from decouple import config
from whyhow import WhyHow

import time 
from basics.custom_exception import WhyHowAIConnectionError, WhyHowAIDataRetrievalError
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.chat_models import ChatOpenAI
from langchain.prompts.chat import ChatPromptTemplate
from backend.logger import Logger
load_dotenv()

workflow_logger = Logger(Logger.WORKFLOW_LOG)


class WhyHowAIRetriever:

    whyhow_cached_obj = None
    def __init__(self, data_source, state):
        try : 

            if WhyHowAIRetriever.whyhow_cached_obj:
                self.__dict__ = WhyHowAIRetriever.whyhow_cached_obj.__dict__
                return 


            start_time = time.time()
            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id

            if self.company:
                self.credentials = CompanySetting.without_company_objects.get(key="KG_WHYHOWAI", company=self.company)
            else:
                self.company = None
                self.credentials = CompanySetting.objects.get(key="KG_WHYHOWAI")
            

            self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}
            
            
            self.whyhowai_base_url = self.credentials_dict.get("whyhowai_base_url") ## load it from env
            self.whyhowai_api_key = self.credentials_dict.get("whyhowai_api_key") 
            self.whyhowai_workspace_id = self.credentials_dict.get("whyhowai_workspace_id")
            self.whyhowai_graph_id = self.credentials_dict.get("whyhowai_graph_id")
            self.openai_api_key = config('OPEN_AI_KEY', default="")

            self.whyhowai_client = WhyHow(api_key=self.whyhowai_api_key, base_url=self.whyhowai_base_url)
            self.workspace = self.whyhowai_client.workspaces.get(workspace_id= self.whyhowai_workspace_id)
            
            self.llm_for_search = ChatOpenAI(temperature=0.0, model="gpt-4o")

            self.user_query_prompt = ChatPromptTemplate.from_template("""Use the information in the context below to create a single, complete answer to the question below:

                                        Question: {question}
                                        Context: {context}
                                    """)

            self.user_query_chain = (
                RunnableParallel(
                    {
                        "context": self.retriever,
                        "question": RunnablePassthrough(),
                    }
                )
                | self.user_query_prompt
                | self.llm_for_search
                | StrOutputParser()
            )
            
            WhyHowAIRetriever.whyhow_cached_obj = self
            workflow_logger.add(f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (WhyHowAI) : [{round(time.time() - start_time, 2)} sec ] whyhowai instance has been initialised")
            
        except Exception as e:
            raise WhyHowAIConnectionError(f"[{self.company.name}]  ({self.session_id}) - could not connect with whyhowai data source")

    

    

    def retriever(self, question: str):
        hybrid_unstructured_query_response = self.whyhowai_client.graphs.query_unstructured(
                graph_id=self.whyhowai_graph_id,
                query=question["question"]
            )

        # Get unique labels, values, and relations
        labels = list({triple.head.label for triple in hybrid_unstructured_query_response.triples} |
                    {triple.tail.label for triple in hybrid_unstructured_query_response.triples})

        values = list({triple.head.name for triple in hybrid_unstructured_query_response.triples} |
                    {triple.tail.name for triple in hybrid_unstructured_query_response.triples})

        relations = list({triple.relation.name for triple in hybrid_unstructured_query_response.triples})

        # Run a structured query with this data
        hybrid_structured_query_response = self.whyhowai_client.graphs.query_structured(
                graph_id=self.whyhowai_graph_id,
                entities=labels,
                relations=relations,
                values=values
            )

        
        return hybrid_structured_query_response.triples


    def query(self, question : str) -> str:
        try : 
            return self.retriever({"question":question}) 

        except Exception as e:
            raise WhyHowAIDataRetrievalError(f"[{self.company.name}]  ({self.session_id}) - could not retrieve data from whyhowai data source")
            return None


