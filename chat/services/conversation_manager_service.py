import asyncio
from chat import utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows.workflow_node import WorkflowLlmNode
from chat.models import ConversationSession, Conversations
from basics.utils import Registry
from backend.constants import CURRENT_API_COMPANY
from django.db import transaction
from asgiref.sync import sync_to_async
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from backend.logger import Logger
redis_logger = Logger(Logger.REDIS_LOG)



class ConversationManagerService:

    SUMMARY_PROMPT_NAME = "summarizer_agent"

    def __init__(self, company=None, api_controller = None):
        if company:
            Registry().set(CURRENT_API_COMPANY, company)
            self.company = company
        else:
            self.company = Registry().get(CURRENT_API_COMPANY)
            
        self.api_controller = api_controller

    """
    all conversation alter function must be created here
    - generate summary
    - fetch summary over session_id    
    - etc
    """
    
    async def get_summarizer_agent(self):
        
        if self.api_controller:
            api_route = self.api_controller.api_route.replace('-','_')
            summarizer_prompt = api_route+'_summarizer_agent'
            return summarizer_prompt
        return self.SUMMARY_PROMPT_NAME

    async def generate_summary(self, company, client_identifier, mobile, extra_save_data):
        from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
        chat_history_service = InMemoryChatHistoryService(company=company)
        
        chat_history = await sync_to_async(chat_history_service.get_chat_history_from_cache)(company=company, client_identifier=client_identifier)
        
        prompt_name = await self.get_summarizer_agent()
        
        if chat_history:
            try:
                llm_info = await sync_to_async(get_active_prompt_from_langfuse)(company.id, prompt_name)
            except Exception as e:
                redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Prompt {self.SUMMARY_PROMPT_NAME} not found : {e}.")

                
                return False
            prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="messages")
            ]
            ).partial(system_prompt=llm_info["system_prompt"])
            workflow_node = WorkflowLlmNode(name=prompt_name,tools={},prompt_name=prompt_name, include_in_final_response=False )
            chat = await sync_to_async(workflow_node.get_llm_class)(llm_info["llm"])
            chat_history_processed = await sync_to_async(utils.strucutre_conversation_langchain)(chat_history, send_tool_args = True, reverse=False)
            chat_history_processed.append(SystemMessage(content="Summarise this conversation"))
            state = {}
            state['messages'] = chat_history_processed
            summary = ""
            try:
                result = asyncio.run(chat.process_request(state, prompt, llm_info, {},company.name, extra_save_data['session_id']))
                summary = result.content
                
                await sync_to_async(self.save_summary)(session_id=extra_save_data['session_id'], client_identifier=client_identifier, summary=summary, company=company, api_controller=self.api_controller)
            except Exception as e:
                redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Error processing summary creation request : {e}.")
                summary = False
            return summary
        return False
    

    def fetch_summary_over_session_id(self, session_id):
        summaries = ConversationSession.objects.filter(session_id=session_id).values("conv_summary")
        return summaries
    
    def fetch_summary_over_client_session_id(self, client_session_id):
        summaries = ConversationSession.objects.filter(client_session_id=client_session_id).values("conv_summary")
        return summaries

    def save_summary(self, session_id, client_identifier, summary, company=None, api_controller=None):
        if company:
            Registry().set(CURRENT_API_COMPANY, company)
        ConversationSession.objects.update_or_create(
            session_id=session_id,
            client_identifier=client_identifier,
            api_controller=api_controller,
            defaults={'conv_summary': summary}
        )

    def validate_conversation_session(self, **kwargs):
        Registry().set(CURRENT_API_COMPANY, self.company)
        session_id = kwargs.get("session_id", None)
        client_session_id = kwargs.get("client_session_id", None)
        client_identifier = kwargs.get("client_identifier", None)
        api_controller = kwargs.get("api_controller", None)
        request_medium = kwargs.get("request_medium", None)
        
        obj, created = ConversationSession.objects.get_or_create(
            client_session_id=client_session_id,
            session_id=session_id,
            client_identifier=client_identifier,
            company=self.company,
            api_controller = api_controller,
            request_medium=request_medium
        )

    def update_client_identifier_over_client_session_id(self, client_identifier, client_session_id):
        from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
        with transaction.atomic():
            if client_session_id:
                """Updating Redis Key"""
                _curr_client_session = ConversationSession.objects.filter(client_session_id=client_session_id).first()
                if _curr_client_session:
                    _curr_client_identifier = _curr_client_session.client_identifier
                    chat_history_service = InMemoryChatHistoryService(company=_curr_client_session.company, api_controller=_curr_client_session.api_controller)
                    chat_history_service._copy_cache_object(_curr_client_session.company,
                                                                    _curr_client_identifier,
                                                                    client_identifier)

                _conv = ConversationSession.objects.filter(client_session_id=client_session_id)
                if _conv:
                    _conv.update(client_identifier=client_identifier)
                    Conversations.objects.filter(client_session_id=client_session_id).update(
                        client_identifier=client_identifier)
                    return True
        return False
