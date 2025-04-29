import asyncio
from datetime import datetime
import json
from chat.utils import strucutre_conversation_langchain
from chat.clients.workflows.common_tools import memory_generator
from chat.clients.workflows.workflow_node import WorkflowLlmNode
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from asgiref.sync import sync_to_async
from backend.constants import CURRENT_API_COMPANY, KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE
from basics.utils import Registry
from chat.assistants import get_active_prompt_from_langfuse
from langchain_core.messages import SystemMessage
from chat.vector_databases.vector_db import VectorDB
from chat.workflow_utils import extract_tool_info
from backend.logger import Logger
from metering.services.openmeter import OpenMeter
from chat.models import ConversationSession
from django.utils import timezone
logger = Logger(Logger.LONG_TERM_MEMORY_GENERATION_INFO)



class LongTermMemoryGenerationService:
    LONG_TERM_MEMORY_PROMPT_NAME = "long_term_memory_creation_agent"
    LONG_TERM_MEMORY_FUNCTION_NAME = "memory_generator"

    def __init__(self, company=None, api_controller=None, openmeter_obj = None):
        if company:
            Registry().set(CURRENT_API_COMPANY, company)
            self.company = company
        else:
            self.company = Registry().get(CURRENT_API_COMPANY)   
        if openmeter_obj:
            self.openmeter_obj = openmeter_obj
        else:
            self.openmeter_obj = OpenMeter(company=self.company)
        
        self.api_controller = api_controller
    
    async def generate_long_term_memory(self, company, client_identifier, session_id, chat_history, vector_storage_provider, workflow_name, workflow_id):
        if chat_history:
            try:
                llm_info = await sync_to_async(get_active_prompt_from_langfuse)(company.id, self.LONG_TERM_MEMORY_PROMPT_NAME)
            except Exception as e:
                logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Prompt {self.SUMMARY_PROMPT_NAME} not found : {e}.")
                
                return False
            prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="messages")
            ]
            ).partial(system_prompt=llm_info["system_prompt"])
            tool_list = []
            save_memory_tool = tool_list.append(memory_generator)

            workflow_node = WorkflowLlmNode(name=self.LONG_TERM_MEMORY_PROMPT_NAME,tools=tool_list,prompt_name=self.LONG_TERM_MEMORY_PROMPT_NAME, include_in_final_response=False )
            
            chat = await sync_to_async(workflow_node.get_llm_class)(llm_info["llm"])
            chat_history_processed = await sync_to_async(strucutre_conversation_langchain)(chat_history, send_tool_args = True, reverse=False)

            workflow_data_for_llm = {
                "workflow_name":workflow_name,
                "workflow_id":workflow_id,
                "company_name":company.name,
                "company_id":company.id,
                "client_identifier" : client_identifier,
                "current_time" : datetime.utcnow().isoformat(),
                "session_id" : session_id
            }
            print(f"\n workflow_data_for_llm : {workflow_data_for_llm} \n")
            chat_history_processed.append(SystemMessage(content=f"Create episodic memory based on the above conversation, here is some user and workflow related data : {json.dumps(workflow_data_for_llm)}"))

            state = {}
            state['company'] = company
            state['messages'] = chat_history_processed
            state['session_id'] = session_id
            state['client_identifier'] = client_identifier
            state['vector_storage_provider'] = vector_storage_provider
            long_term_memory = ""
            try:
                result = asyncio.run(chat.process_request(state, prompt, llm_info, tool_list, company.name, session_id))
                print(f"\n Result from LLM : {result} \n")
                tool_calls = result.additional_kwargs.get('tool_calls',[])
                tool_info = extract_tool_info(tool_calls)
                cypher_script = []
                for name, args in tool_info:
                    tool_name = name
                    arguments = args

                    if tool_name == self.LONG_TERM_MEMORY_FUNCTION_NAME:
                        cypher_queries = arguments.get("cypher_queries", None)
                        cypher_script.append(cypher_queries)

                combined_cypher_script = "\n".join(cypher_script)
                if combined_cypher_script:
                    save_memory = await self.save_memory_using_cypher_script(cypher_script=combined_cypher_script, company=company, vector_storage_provider=vector_storage_provider, session_id=session_id)
            except Exception as e:
                logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Error processing summary creation request : {e}.")
            return True
        return False
    
    async def save_memory_using_cypher_script(self, cypher_script, company, vector_storage_provider, session_id):
        print(f"\n all save_memory_using_cypher_queries : {cypher_script}\n")
        provider_factory = VectorDB(company=company)
        provider_class = await sync_to_async(provider_factory.get_vector_database)(vector_storage_provider, openmeter_obj=self.openmeter_obj)
        await provider_class.run_cypher_script(cypher_script=cypher_script)
        await self.mark_episodic_memory_created(session_id=session_id)
        
        return True
    
    async def mark_episodic_memory_created(self, session_id):
        updated_rows =  await sync_to_async(ConversationSession.objects.filter(
            session_id=session_id,
            company=self.company
        ).update)(
            is_episodic_memory_created=True,
            episodic_memory_created_at=timezone.now()
        )
        if updated_rows == 0:
            print(f"Warning: No session found with session_id={session_id} for company={self.company}")
    
        return updated_rows
    
    def push_data_to_long_term_memory_generation_queue(self, queue_data):
        from backend.services.kafka_service import BaseKafkaService
        BaseKafkaService().push(KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE, queue_data)
