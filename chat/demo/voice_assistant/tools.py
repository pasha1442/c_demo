from typing import Annotated
from asgiref.sync import sync_to_async
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from backend.logger import Logger
from chat.clients.workflows.agent_state import PipelineState

workflow_logger = Logger(Logger.WORKFLOW_LOG)

tools = [
    {
        "name": "save_feedback_database",
        "description": "saves feedback in db",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "feedback data to be saved",
                },
            },
            "required": ["data"],
            "additionalProperties": False,
        },
        "type": "function"
    }
]

@tool
async def save_feedback(data:str, state: Annotated[dict, InjectedState]):
    """
    save the feedback in the database.

    Args:
        data : feedback data to be saved
    """
    from chat.services.conversation_manager_service import ConversationManagerService 
    # context = state['workflow_context']
    context = PipelineState.get_workflow_context_object_from_state(state)
    api_controller = context.openmeter_obj.api_controller
    try:
        from chat.services.conversation_manager_service import ConversationManagerService
        conv_manager = ConversationManagerService(company=context.company, api_controller=api_controller)
        await sync_to_async(conv_manager.save_summary)(session_id=context.session_id, client_identifier=context.mobile, summary=data, api_controller=api_controller)
        workflow_logger.add(f"session_id: {context.session_id} | Summary saved successfully")
        return "Feedback saved successfully"
    except Exception as e:
        workflow_logger.add(f"session_id: {context.session_id} | Error while saving summary: {e}")
        return f"Error while saving feedback: {e}"
    
    
    
    
@tool
async def save_feedback_database(data, phone_number=None, session_id = None, state: Annotated[dict, InjectedState]=[]):
    """
    save the feedback in the database.

    Args:
        data : feedback data to be saved
    """
    context = PipelineState.get_workflow_context_object_from_state(state)
    api_controller = context.openmeter_obj.api_controller
    try:
        from chat.services.conversation_manager_service import ConversationManagerService
        conv_manager = ConversationManagerService(company=context.company, api_controller=api_controller)
        await sync_to_async(conv_manager.save_summary)(session_id=session_id, client_identifier=phone_number[3:], summary=data, api_controller_id=api_controller)
        workflow_logger.add(f"session_id: {session_id} | Summary saved successfully")
    except Exception as e:
        workflow_logger.add(f"session_id: {session_id} | Error while saving summary: {e}")