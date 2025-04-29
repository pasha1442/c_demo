from langchain.chat_models import ChatOpenAI
from chat.clients.workflows.agent_state import PipelineState
from company.models import CompanySetting
import time
from langchain_core.prompts.prompt import PromptTemplate
from chat.assistants import get_active_prompt_from_langfuse
from basics.custom_exception import SQLDBConnectionError, SQLDataRetrievalError
import nest_asyncio
from langfuse.decorators import observe
from chat.workflow_utils import push_llminfo_to_openmeter
from services.services.base_agent import BaseAgent
nest_asyncio.apply()
from chat.retriever.factory.sql_factory import MySQLFactory
from chat.retriever.base_retriever import BaseRetriever
import traceback
from chat.retriever.factory.bigquery_factory import BigQueryFactory

from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)

class SQLRetriever(BaseRetriever):

    def __init__(self, data_source, state):
        try:

            start_time = time.time()
            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id

            if self.company:
                self.company = self.company
                self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_KB_SQL_CREDENTIALS, company=self.company)
            else:
                self.company = None
                self.credentials = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_KB_SQL_CREDENTIALS)

            self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}

            self.database_api_key = self.credentials_dict.get("database_api_key")  
            self.database_api_url = self.credentials_dict.get("database_api_url")

            
            self.openmeter_obj = context.openmeter
            self.data_source = data_source
            self.sql_query_builder_llm_info = get_active_prompt_from_langfuse(self.company.id, "sql_query_builder")

            self.SQL_GENERATION_PROMPT = PromptTemplate(
                input_variables=["schema", "question"], template=self.sql_query_builder_llm_info["system_prompt"]
            )

            self.sql_query_chain = self.SQL_GENERATION_PROMPT | ChatOpenAI(temperature=0, model="gpt-4o")

            self.schema = get_active_prompt_from_langfuse(self.company.id, "sql_db_schema")["system_prompt"]


        except Exception as e:
            # print(e, traceback.print_exc())
            raise SQLDBConnectionError(
                f"[{self.company.name}] ({self.session_id}) - SQLRetriever Could not connect with sql data source due to {e}")



    def extract_sql(self, text: str) -> str:
        sql_query = text.strip()  
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        sql_query = sql_query.replace("\n", " ")
        return sql_query

    def query_database(self, sql_query):
        headers = {
            'Content-Type': 'application/json'
            }
        arg_data = {
            "query": sql_query,
            "api_key": self.database_api_key
            }

        api_res = BaseAgent(company=self.company,agent_slug=f"api_agent.{str.lower(self.company.name)}_sql_query_api").invoke_agent(args=arg_data, ai_args={})
        return api_res["data"]
        
    def structured_retriever(self, question: str) -> str:
        structured_search = self.sql_query_chain.invoke({"question": question, "schema": self.schema})
        sql_query = self.extract_sql(structured_search.content)
        structured_search_resp = self.query_database(sql_query)

        return structured_search, sql_query, structured_search_resp


    @observe()
    def retriever(self, question: str):
        workflow_logger.add(f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (SQL) : Search-Query {question}")

        t1 = time.time()

        structured_search, sql_query, structured_search_resp = self.structured_retriever(question["question"])
        push_llminfo_to_openmeter(
            node_data={"messages": [structured_search], "llm_info": self.sql_query_builder_llm_info},
            openmeter_obj=self.openmeter_obj)
        
        full_response = f"structured response :\n SQL Query - {sql_query}\n Query Response - {structured_search_resp}"
        
        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (SQL) : [{round(time.time() - t1, 2)} sec ] Final Search Result {full_response}")
        return full_response

    def query(self, question: str) -> str:

        try:
            return self.retriever({"question": question})

        except Exception as e:
            raise SQLDataRetrievalError(
                f"[{self.company.name}] ({self.session_id})- Could not retrieve data from sql data source, {str(e)}")
            return None


class AdvSQLRetriever(BaseRetriever):

    def __init__(self, data_source, state):
        try:

            start_time = time.time()
            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id
            self.openmeter_obj = context.openmeter
            self.data_source = data_source
            self.sql_connection = MySQLFactory.get_mysql_instance(self.company)

            self.sql_query_builder_llm_info = get_active_prompt_from_langfuse(self.company.id, "sql_query_builder")

            self.SQL_GENERATION_PROMPT = PromptTemplate(
                input_variables=["schema", "question"], template=self.sql_query_builder_llm_info["system_prompt"]
            )

            self.sql_query_chain = self.SQL_GENERATION_PROMPT | ChatOpenAI(temperature=0, model="gpt-4o")

            self.schema = get_active_prompt_from_langfuse(self.company.id, "sql_db_schema")["system_prompt"]


        except Exception as e:
            raise SQLDBConnectionError(
                f"[{self.company.name}] ({self.session_id}) - AdvSQLRetriever Could not connect with sql data source due to {e}")



    def extract_sql(self, text: str) -> str:
        sql_query = text.strip()  
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        return sql_query

    def query_database(self, sql_query):
        return self.sql_connection.query_database(sql_query)
        
    def structured_retriever(self, question: str) -> str:
        structured_search = self.sql_query_chain.invoke({"question": question, "schema": self.schema})
        sql_query = self.extract_sql(structured_search.content)
        structured_search_resp = self.query_database(sql_query)

        return structured_search, sql_query, structured_search_resp


    @observe()
    def retriever(self, question: str):
        workflow_logger.add(f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (SQL) : Search-Query {question}")

        t1 = time.time()

        structured_search, sql_query, structured_search_resp = self.structured_retriever(question["question"])
        push_llminfo_to_openmeter(
            node_data={"messages": [structured_search], "llm_info": self.sql_query_builder_llm_info},
            openmeter_obj=self.openmeter_obj)
        
        full_response = f"structured response :\n SQL Query - {sql_query}\n Query Response - {structured_search_resp}"
        
        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (SQL) : [{round(time.time() - t1, 2)} sec ] Final Search Result {full_response}")
        return full_response

    def query(self, question: str) -> str:

        try:
            return self.retriever({"question": question})

        except Exception as e:
            raise SQLDataRetrievalError(
                f"[{self.company.name}] ({self.session_id})- Could not retrieve data from sql data source")
            

class BigQueryRetriever(BaseRetriever):

    def __init__(self, data_source, state):
        try:

            start_time = time.time()
            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id
            self.openmeter_obj = context.openmeter
            self.data_source = data_source
            self.bigquery_connection = BigQueryFactory.get_bigquery_instance(self.company)

            try:
                self.sql_query_builder_llm_info = get_active_prompt_from_langfuse(self.company.id, "sql_query_builder")
                self.SQL_GENERATION_PROMPT = PromptTemplate(
                    input_variables=["schema", "question"], template=self.sql_query_builder_llm_info["system_prompt"]
                )
                self.sql_query_chain = self.SQL_GENERATION_PROMPT | ChatOpenAI(temperature=0, model="gpt-4o")
                self.schema = get_active_prompt_from_langfuse(self.company.id, "sql_db_schema")["system_prompt"]
            except Exception as e:
                workflow_logger.add(f"[{self.company}] ({self.session_id}) Warning: Failed to set up SQL generation chain: {e}]")
                self.sql_query_builder_llm_info = {"system_prompt": "Generate SQL based on schema and question."}
                self.SQL_GENERATION_PROMPT = PromptTemplate(
                    input_variables=["schema", "question"], template=self.sql_query_builder_llm_info["system_prompt"]
                )
                self.sql_query_chain = self.SQL_GENERATION_PROMPT | ChatOpenAI(temperature=0, model="gpt-4o")
                self.schema = ""
        except Exception as e:
            raise SQLDBConnectionError(
                f"[{self.company.name}] ({self.session_id}) - BigQueryRetriever Could not connect with big query data source {e}")



    def extract_sql(self, text: str) -> str:
        sql_query = text.strip()  
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        return sql_query

    def query_database(self, sql_query):
        return self.bigquery_connection.query_database(sql_query)
        
    def structured_retriever(self, question: str) -> str:
        structured_search = self.sql_query_chain.invoke({"question": question, "schema": self.schema})
        sql_query = self.extract_sql(structured_search.content)
        structured_search_resp = self.query_database(sql_query)

        return structured_search, sql_query, structured_search_resp


    @observe()
    def retriever(self, question: str):
        workflow_logger.add(f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (SQL) : Search-Query {question}")

        t1 = time.time()

        structured_search, sql_query, structured_search_resp = self.structured_retriever(question["question"])
        push_llminfo_to_openmeter(
            node_data={"messages": [structured_search], "llm_info": self.sql_query_builder_llm_info},
            openmeter_obj=self.openmeter_obj)
        
        full_response = f"structured response :\n SQL Query - {sql_query}\n Query Response - {structured_search_resp}"
        
        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (SQL) : [{round(time.time() - t1, 2)} sec ] Final Search Result {full_response}")
        return full_response

    def query(self, question: str) -> str:

        try:
            return self.retriever({"question": question})

        except Exception as e:
            # print(traceback.print_exc())
            raise SQLDataRetrievalError(
                f"[{self.company.name}] ({self.session_id})- Could not retrieve data from big query data source")

    @observe
    def sql_executor(self, sql_query:str):
        workflow_logger.add(f"SQL Executor [{self.company}] ({self.session_id}) -> (SQL) : Query : {sql_query}")
        try:
            sql_resp = self.query_database(sql_query)
        except Exception as e:
            workflow_logger.add(f"[{self.company.name}] ({self.session_id}) - Could not retrieve data from big query {sql_query} data source due to : {e}")
            raise SQLDataRetrievalError(
                f"[{self.company.name}] ({self.session_id}) - Could not retrieve data from big query {sql_query} data source due to : {e}")
        
        return sql_resp
