from datetime import datetime, timedelta, timezone
import json
import time
from typing import Annotated, List
from langchain_core.tools import tool
import pytz
from backend.constants import CURRENT_API_COMPANY
from basics.utils import Registry
from chat import utils
from chat.clients.workflows.agent_state import PipelineState
from chat.constants import WAHA_SERVER_BASE_URL
from chat.models import ConversationSession
from chat.retriever.base_retriever import BaseRetriever
from chat.retriever.neo4j_retriever import Neo4jRetriever, AdvancedNeo4jRetriever
from chat.retriever.sql_retriever import SQLRetriever, AdvSQLRetriever, BigQueryRetriever
from chat.retriever.pinecone_retriever import PineconeRetriever
from chat.retriever.whyhowai_retriever import WhyHowAIRetriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import pinecone
import asyncio
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from chat.workflow_utils import get_context
from langfuse.decorators import observe
from langgraph.prebuilt import InjectedState
from backend.logger import Logger
from chat.assistants import get_active_prompt_from_langfuse
from chat.workflow_utils import push_llminfo_to_openmeter
from chat.llms.openai import Openai
from company.utils import CompanyUtils
from services.services.base_agent import BaseAgent
from langchain_core.messages import AIMessage
import requests
from basics.custom_exception import Neo4jConnectionError, Neo4jDataRetrievalError
import traceback
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


workflow_logger = Logger(Logger.WORKFLOW_LOG)



@tool
def search_document_archive_for_info(query: str) -> str:
    """
    Searches the document archive for information realted to user query

    Args:
        query : query of the user
    """
    try:
        context = get_context()
        Registry().set(CURRENT_API_COMPANY, context.company)
        query_embedding = utils.create_embedding(query)
        vectordb_host = utils.get_vectordb_host()
        vector_db_init = utils.init_vectordb_host(vectordb_host)
        if not (vector_db_init):
            #raise exception
            pass
        
        index = pinecone.Index(vector_db_init.get('index'))
        namespace = vector_db_init.get('namespace')
        if namespace:
            response = index.query(vector=query_embedding,top_k=2, include_metadata=True, namespace=namespace)
        else:
            response = index.query(vector=query_embedding,top_k=2, include_metadata=True)
        matches = response['matches']
        info = ''
        for match in matches:
            info += match['metadata']['text']

        return f"Information found in the archive : {info}"
    except Exception as e:
        print(f"Failed to fetch information from db: {str(e)}")
        return f"Failed to execute. Error: {repr(e)}"
    
    
@tool()
@observe()
def knowledge_retriver(query:str, topk:int, state: Annotated[dict, InjectedState], data_source:str) -> str:

    """
    Retrieves data from the pinecone index

    Args:
        query : string value for retrieving relevant data
        topk : top k results
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    workflow_logger.add(f" [{context.company.name}]  ({context.session_id})  Knowledge-Retriever -> (tool) -> : data_source - {data_source}")
    
    
    if data_source == "pinecone" : 
        retriever = PineconeRetriever(data_source, state)
        
    elif data_source == "kg_neo4j":
        retriever = Neo4jRetriever(data_source, state)
        

    elif data_source == "structure_kg_neo4j":
        retriever = AdvancedNeo4jRetriever(data_source = data_source, state = state)

    elif data_source == "sql_retriever":
        retriever = SQLRetriever(data_source, state)

    elif data_source == "adv_sql_retriever":
        retriever = AdvSQLRetriever(data_source, state)
        

    elif data_source == "whyhowai":
        retriever = WhyHowAIRetriever(data_source, state)

    elif data_source == "big_query":
        retriever = BigQueryRetriever(data_source, state)

    info = retriever.query(query)
    return info

@tool()
@observe()
def structured_retriever(query: str, topk: int = 5, state: Annotated[dict, InjectedState] = None) -> str:
    """
    Retrieves data using structured Cypher queries for questions with clearly identifiable entities and relationships.
    Best for queries that can be answered by directly matching graph patterns.
    
    Args:
        query: The user's question/query that contains specific entities or relationships
        topk: Maximum number of results to return
        state: The workflow state
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    workflow_logger.add(f"[{context.company.name}] ({context.session_id}) Structured-Retriever -> Query: {query}")
        
    t1 = time.time()
    
    try:
        retriever = AdvancedNeo4jRetriever(data_source="structure_kg_neo4j", state=state)
        
        structured_search, cypher_query, structured_results = retriever.structured_retriever(query)
        
        print("CYPHER QUERY: ", cypher_query)
        print("RESULTS: ", structured_results)
        
        if structured_search is None:
            return f"Error executing structured query: {cypher_query}"
            
        response = f"CYPHER QUERY: {cypher_query}\n\nRESULTS: {structured_results}"
        
        workflow_logger.add(
            f"[{context.company.name}] ({context.session_id}) Structured-Retriever -> [{round(time.time() - t1, 2)}s] Results found"
        )
        
        return response
    
    except Exception as e:
        error_msg = f"Error in structured_retriever tool: {str(e)}"
        workflow_logger.add(f"[{context.company.name}] ({context.session_id}) Structured-Retriever Error: {error_msg}")
        return f"Error: {str(e)}\n Please fix your mistakes."
    

@tool()
@observe()
def unstructured_retriever(query: str, topk: int = 5, state: Annotated[dict, InjectedState] = None) -> str:
    """
    Retrieves data using pre-defined vector search queries for abstract, preference-based questions.
    Best for open-ended, conceptual queries or recommendations without direct mappings.
    
    Args:
        query: The user's conceptual or preference-based question
        topk: Maximum number of results to return
        state: The workflow state
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    workflow_logger.add(f"[{context.company.name}] ({context.session_id}) Unstructured-Retriever -> Query: {query}")
    
    t1 = time.time()
    
    try:
        retriever = AdvancedNeo4jRetriever(data_source="structure_kg_neo4j", state=state)
        
        unstructured_results = retriever.unstructured_retriever(query)
        
        response = f"SEMANTIC SEARCH RESULTS:\n{unstructured_results}"
        
        workflow_logger.add(
            f"[{context.company.name}] ({context.session_id}) Unstructured-Retriever -> [{round(time.time() - t1, 2)}s] Results found"
        )
        
        return response
    
    except Exception as e:
        error_msg = f"Error in unstructure_retriever tool: {str(e)}"
        workflow_logger.add(f"[{context.company.name}] ({context.session_id}) Unstructured-Retriever Error: {error_msg}")
        return f"Error: {str(e)}\n Please fix your mistakes."

@tool()
@observe()
def hybrid_retriever(query: str, topk: int = 5, state: Annotated[dict, InjectedState] = None) -> str:
    """
    Retrieves data using both structured and vector-based approaches for complex queries.
    Best for queries that combine specific entities with conceptual or contextual needs.
    
    Args:
        query: The user's complex question with both specific entities and contextual needs
        topk: Maximum number of results to return
        state: The workflow state
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    workflow_logger.add(f"[{context.company.name}] ({context.session_id}) Hybrid-Retriever -> Query: {query}")
    
    t1 = time.time()
    
    retriever = AdvancedNeo4jRetriever(data_source="structure_kg_neo4j", state=state)
    
    response = retriever.retriever(query)
    
    workflow_logger.add(
        f"[{context.company.name}] ({context.session_id}) Hybrid-Retriever -> [{round(time.time() - t1, 2)}s] Results found"
    )
    
    return response

@tool
@observe()
def get_db_schema(state: Annotated[dict, InjectedState]) -> str:
    """
    Fetches Neo4j database schema and indexes directly from the database.
    
    This tool provides comprehensive information about:
    - Complete database schema (nodes, relationships, properties) 
    - Vector indexes with their configurations
    - Fulltext indexes with their configurations
    
    """
    
    
    try:
        context = PipelineState.get_workflow_context_object_from_state(state)
        company = context.company
        session_id = context.session_id
        
        workflow_logger.add(f"Neo4j Schema Tool [{company}] ({session_id}) -> Fetching schema and indexes")
        
        retriever = AdvancedNeo4jRetriever(data_source="structure_kg_neo4j", state=state)
        
        result = retriever.get_schema()
        
        workflow_logger.add(f"Neo4j Schema Tool [{company}] ({session_id}) -> Completed")
        
        return result
        
    except Exception as e:
        context = PipelineState.get_workflow_context_object_from_state(state)
        error_msg = f"Error in get_neo4j_schema_and_indexes tool: {str(e)}"
        workflow_logger.add(f"Neo4j Schema Tool [{context.company}] ({context.session_id}) -> Error: {error_msg}")
        traceback.print_exc()
        
        return f"Error fetching Neo4j database schema and indexes: {str(e)}"
    
@tool
@observe()
def neo4j_cypher_executor(cypher_query: str, state: Annotated[dict, InjectedState] = None) -> str:
    """
    Executes a Cypher query against Neo4j database.

    Args:
        cypher_query: The Cypher query to execute
        state: The workflow state containing context information
    
    Returns:
        Formatted results from the Neo4j query execution
    """
    try:
        
        
        context = PipelineState.get_workflow_context_object_from_state(state)
        
        retriever = AdvancedNeo4jRetriever(data_source="structure_kg_neo4j", state=state)
        
        result = retriever.execute_cypher_query(cypher_query)
        
        return result
        
    except Exception as e:
        context = PipelineState.get_workflow_context_object_from_state(state)
        error_msg = f"Error in neo4j_cypher_executor: {str(e)}"
        workflow_logger.add(f"Neo4j Executor [{context.company}] ({context.session_id}) -> Critical error: {error_msg}")
        traceback.print_exc()
        
        return f"Error executing Neo4j query: {str(e)}"
    
@tool
@observe
def sql_executor(sql_query:str, state: Annotated[dict, InjectedState], data_source:str = "big_query") -> str:
    """
    Executes the SQL QUERY

    Args:
        sql_query : sql query to run
    """
    base_retriever = BaseRetriever()
    retriever = base_retriever.get_retriever(data_source, state)
    sql_response = retriever.sql_executor(sql_query)

    return sql_response

@tool
@observe()
def recommend_books(query:str, topk:int) -> str:
    """
    Recommend books

    Args:
        query : string value for retrieving relevant data
        topk : top k results
    """
    result = """
    Here are the recommended books, only provide from this not others
    1. Bhagavad-gītā As It Is
    2. The yoga of the Bhagavad Gita
    3. Srimad Bhagvad Gita English
    """
    return result


@tool()
@observe()
def api_connector(query:str, state: Annotated[dict, InjectedState], additional_args = {}) -> str:

    """
    Used to handle api requests.

    Args:
        query : string value for retrieving relevant data
        additional_args : dictionary containing additional arguments user wants to send.
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    workflow_logger.add(f" [{context.company.name}]  ({context.session_id})  API-Agent -> (tool)")

    # context = state['workflow_context']
    CompanyUtils.set_company_registry(context.company)
    agent_name = state["messages"][-1].name
    
    arg_data = {
        "args" : additional_args,
        "query": query
    }

    api_res = BaseAgent(company=context.company,agent_slug=f"api_agent.{agent_name}").invoke_agent(args=arg_data, ai_args={})
    return json.dumps(api_res)



@tool()
@observe()
def image_analyser(query:str, state: Annotated[dict, InjectedState]) -> str:
    """
    Used to handle image based question.
    Args:
        query : detailed string query that needs to be passed as task of the image analyser tool. 
    """
    context = PipelineState.get_workflow_context_object_from_state(state)

    workflow_logger.add(f" [{context.company.name}]  ({context.session_id})  API-Agent -> (tool)")

    # context = state['workflow_context']
    CompanyUtils.set_company_registry(context.company)
    agent_name = state["messages"][-1].name
    chat = Openai()
    context = PipelineState.get_workflow_context_object_from_state(state)
    company = context.company
    openmeter_obj = context.openmeter
    session_id = context.session_id
    image_analyser_llm_info = get_active_prompt_from_langfuse(company.id, f"{agent_name}_image_analyser")
    image_analyser_llm_info["system_prompt"] = image_analyser_llm_info["system_prompt"].format(query)
    prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="messages")
            ]
        ).partial(system_prompt=image_analyser_llm_info["system_prompt"])
    
    

    last_tool_message = state['messages'][-1]
    state['messages'] = state['messages'][:-1]

    result = asyncio.run(chat.process_request(state, prompt, image_analyser_llm_info, [], context.company.name, context.session_id))
    push_llminfo_to_openmeter(
            node_data={"messages": [result], "llm_info": image_analyser_llm_info},
            openmeter_obj=openmeter_obj)
    state['messages'].append(last_tool_message)

    workflow_logger.add(f"image analyser [{company}] ({session_id}) -> (Image Analyser)) :  Result {result}")

    return result.content


@tool
def memory_retriever(query:str, topk:int, state: Annotated[dict, InjectedState], data_source:str="neo4j"):
    """
        Retreives user specific stored memories
        Args:
            query : query to look for in stored memories
            topk : how many memories to retrieve, default 3
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    base_retriever = BaseRetriever()
    retriever = base_retriever.get_retriever(data_source, state)
    info = retriever.query(query=query, extra_params=context.extra_save_data)
    return info

@tool
def memory_generator(cypher_queries:str, state: Annotated[dict, InjectedState]):
    """
    Maintains an episodic memory system within a Neo4j knowledge graph.

    Args:
        cypher_queries (str): A string containing Cypher queries to run on the Neo4j database.

    Functionality:
        - Connects to the Neo4j database.
        - Executes the provided Cypher queries.
        - Handles errors and logs query execution.
    """
    pass




def waha_check_for_message_ignorance(state: Annotated[dict, InjectedState]):
    """
    Checks if the message is to be ignored by WhyHowAI

    Args:
        state : state of the workflow
    """
    print("inside waha check")
    workflow_logger.add("inside waha check")
    context = PipelineState.get_workflow_context_object_from_state(state)
    print("session id: ", context.session_id)
    print("session:", state["workflow_context"]["session_id"])
    
    Registry().set(CURRENT_API_COMPANY, context.company)
    session = ConversationSession.objects.filter(session_id=context.session_id, company_id=context.company.id).first()
    ignore_session = session.ignore_session
    print("hello ji ki haal chaal", ignore_session)
    #Condition 1: check for ignore flag
    if ignore_session:
        return {"messages": [AIMessage(content="ignore", name="__workflow_start__")], "sender": "__workflow_start__", "workflow_context": state["workflow_context"], "include": "no"}
    
    workflow_logger.add(f"Condition passed: check ignore_session: {ignore_session}")
    print(f"Condition passed: check ignore_session: {ignore_session}")
    
    # session_messages = Conversations.objects.filter(session_id=context.session_id, company_id=context.company.id).values_list('role', 'message', 'created_at')
    session_messages = utils.fetch_conversation_by_session_id(context.session_id, context.company)
    
    last_valid_user_message_time = datetime.now(timezone.utc)
    system_unreplied_customer_messesage_count = 0
    system_assistant_messages_count = 0
    for idx, message in enumerate(session_messages):
        if message['role'] == 'assistant' or message['role'] == 'function': 
            for i, message1 in enumerate(session_messages):
                if i < idx: continue
                if message1['role'] == 'user': break
                elif message1['role'] == 'assistant': system_assistant_messages_count += 1

            break
        last_valid_user_message_time = datetime.strptime(message['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
        system_unreplied_customer_messesage_count += 1
    
    
    #Condition 2: Check if human agent has started to communicate with customer
    agent_phone_number = state["workflow_context"]["message_payload"]["company_phone_number"]
    customer_phone_number = state["workflow_context"]["mobile"]
    
    waha_session = state["workflow_context"]["message_payload"]["waha_session"]
    
    url = f"{WAHA_SERVER_BASE_URL}/api/{waha_session}/chats/{customer_phone_number}/messages"
    params = {"downloadMedia": "false","limit": 5}

    messages = []
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for HTTP error responses (4xx, 5xx)
        messages = response.json()  # Parse response JSON
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        
    waha_unreplied_customer_messesage_count = 0
    waha_assistant_message_count = 0
    for idx, message in enumerate(messages):
        if message['from'] == agent_phone_number+"@c.us": 
            for idx2, message2 in enumerate(messages):
                if idx2 < idx: continue
                if message2['from'] != agent_phone_number+"@c.us" or system_assistant_messages_count == 0: break
                waha_assistant_message_count += 1
            break
        waha_unreplied_customer_messesage_count += 1
    
    workflow_logger.add(f"waha_unreplied_messesage_count: {waha_unreplied_customer_messesage_count}, system_unreplied_messesage_count: {system_unreplied_customer_messesage_count}")
    workflow_logger.add(f"waha_assistant_message_count: {waha_assistant_message_count}, system_assistant_messages_count: {system_assistant_messages_count}")

    if waha_unreplied_customer_messesage_count < system_unreplied_customer_messesage_count or waha_assistant_message_count > system_assistant_messages_count:
        if not session.ai_takeover_session:
            session.ignore_session = True
            session.save(update_fields=["ignore_session"])
            return {"messages": [AIMessage(content="ignore", name="__workflow_start__")], "sender": "__workflow_start__", "workflow_context": state["workflow_context"], "include": "no"}
        else:
            session.ai_takeover_session = False
            session.save(update_fields=["ai_takeover_session"])
    
    workflow_logger.add(f"Condition passed: No actual human agent intervention.")
    print(f"Condition passed: No actual human agent intervention.")
    
    #Condition 3: check if latest user messages came under 5 minutes
    
    first_waiting_time = 60*5
    second_waiting_time = 0
    api_controller = state["workflow_context"]["openmeter"]["api_controller"]
    if api_controller["auth_credentials"] and api_controller["auth_credentials"]["config"]:
        first_waiting_time = api_controller["auth_credentials"]["config"]["first_waiting_time_in_seconds"]
        second_waiting_time = api_controller["auth_credentials"]["config"]["second_waiting_time_in_seconds"]
    
    ist_time = last_valid_user_message_time.astimezone(pytz.timezone('Asia/Kolkata')).timestamp()
    
    if system_unreplied_customer_messesage_count == len(session_messages):
        if time.time() - ist_time < first_waiting_time:
            return {"messages": [AIMessage(content="ignore", name="__workflow_start__")], "sender": "__workflow_start__", "workflow_context": state["workflow_context"], "include": "no"}
    else:
        if time.time() - ist_time < second_waiting_time:
            return {"messages": [AIMessage(content="ignore", name="__workflow_start__")], "sender": "__workflow_start__", "workflow_context": state["workflow_context"], "include": "no"}
    
    workflow_logger.add(f"Condition passed: message arrived {ist_time/60} minutes ago.")
    print(f"Condition passed: message arrived {ist_time/60} minutes ago.")
    
    return {
            "messages": [AIMessage(content="don't ignore", name="__workflow_start__")],
            "sender": "__workflow_start__", 
            "workflow_context": state["workflow_context"],
            "include": "no"
        }

@tool(return_direct=False)
def waha_find_running_sessions():
    """
        Retreives running whatsapp sessions
    """
    url = f"http://0.0.0.0:3002/api/sessions"
    params = {"all": False}

    sessions = []
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for HTTP error responses (4xx, 5xx)
        sessions = response.json()  # Parse response JSON
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    
    # response = []
    for session in sessions:
        del session['status']
        
    return sessions

from django.db.models import Max

@tool(return_direct=False)
def start_or_stop_waha_session_assistant(session_names: List[str], is_enable: bool, state: Annotated[dict, InjectedState]):
    """
        enable or disable whatsapp session assistant
        Args:
            sessions_names : names of the sessions
            is_enable : True or False, True if user wants to enable session and False if user wants to disable sessions
    """
    from django.utils import timezone
    print(session_names)
    context = PipelineState.get_workflow_context_object_from_state(state)
    Registry().set(CURRENT_API_COMPANY, context.company)
     
    for session_name in session_names:
        start_time_threshold = timezone.now() - timedelta(hours=6)
        latest_sessions = (
            ConversationSession.objects
            .filter(client_session_id=session_name, company_id=context.company.id, created_at__gte=start_time_threshold, request_medium='waha')
            .values('client_identifier')
            .annotate(latest_created_at=Max('created_at'))
        )
        sessions = ConversationSession.objects.filter(
            client_session_id=session_name,
            company_id=context.company.id,
            created_at__gte=start_time_threshold,
            request_medium='waha',
            created_at__in=[s['latest_created_at'] for s in latest_sessions]
        )
        
        print(sessions)

            # sessions = ConversationSession.objects.filter(client_session_id=session_name, company_id=context.company.id, created_at__gte=start_time_threshold, request_medium='waha')
        if is_enable: 
            for session in sessions:
                # client_identifier = session.client_identifier
                # in_memory_chat_service = InMemoryChatHistoryService()
                
                # cache_key = in_memory_chat_service._get_cache_key(context.company, client_identifier)
                # new_session_id = in_memory_chat_service.session_handler._generate_new_session_id(context.company)
                # success = in_memory_chat_service.cache_service.hset(cache_key, "session_id", new_session_id)
                
                # print("Success:", success)
                
                session.ignore_session = False
                session.ai_takeover_session = True
                session.save(update_fields=["ignore_session", "ai_takeover_session"])
            return "Enabled"
        else:    
            for session in sessions:
                session.ignore_session = True
                session.save(update_fields=["ignore_session"])
            return "Disabled"
    # return "Stop"