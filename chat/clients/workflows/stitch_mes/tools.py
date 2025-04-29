from chat.retriever.sql_retriever import SQLRetriever
from services.services.base_agent import BaseAgent
from chat.clients.workflows.agent_state import PipelineState
from basics.custom_exception import SQLDataRetrievalError
from chat.workflow_utils import push_llminfo_to_openmeter
from langchain_core.tools import tool
import time
from backend.logger import Logger
from typing import Annotated
from langgraph.prebuilt import InjectedState
import traceback

workflow_logger = Logger(Logger.WORKFLOW_LOG)



@tool
def stitch_sql_retriever(query:str, state: Annotated[dict, InjectedState], data_source:str) -> str:

    """

    Args:
        query : user detailed natural query 
    """
    t1 = time.time()
    retriever = SQLRetriever(data_source, state)

    try:

        structured_search = retriever.sql_query_chain.invoke({"question": query, "schema": retriever.schema})
        user_mobile_number = context = PipelineState.get_workflow_context_object_from_state(state).mobile
        user_profile_api_key = retriever.credentials_dict.get("user_profile_api_key")
        user_data = {"mobile" : user_mobile_number, "api_key" : user_profile_api_key}
        
        api_res = BaseAgent(company=retriever.company,agent_slug=f"api_agent.fetch_user_profile").invoke_agent(args=user_data, ai_args={})
        
        
        if not api_res:
            raise Exception("User could not be authorised")
        
        else:
            sql_query = retriever.extract_sql(structured_search.content)
            formatted_sql_query = sql_query.replace("<company_id>" ,  str(api_res.get("data", "").get("company_id", -1))) 
            formatted_sql_query = formatted_sql_query.replace("<company_name>" ,  api_res.get("data", "").get("name", -1)) 
        
            structured_search_resp = retriever.query_database(formatted_sql_query)

            push_llminfo_to_openmeter(
                node_data={"messages": [structured_search], "llm_info": retriever.sql_query_builder_llm_info},
                openmeter_obj=retriever.openmeter_obj)
            
            full_response = f"structured response :\n SQL Query - {formatted_sql_query}\n Query Response - {structured_search_resp}"
            
            workflow_logger.add(
                f"Stitch-SQL-Retriever [{retriever.company}] ({retriever.session_id}) -> (SQL) : [{round(time.time() - t1, 2)} sec ] Final Search Result {full_response}")
            return full_response


    except Exception as e:
        raise SQLDataRetrievalError(
            f"[{retriever.company.name}] ({retriever.session_id})- Could not retrieve data from sql data source, {str(e)}")
