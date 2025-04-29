import json
import re
from typing import Dict, List, Optional, Tuple
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
import functools
from backend.constants import API_MOBILE, CURRENT_API_COMPANY, OPENMETER_GLOBAL_OBJ
from basics.custom_exception import IncorrectSurveyError
from basics.utils import Registry
from chat import utils
from chat import workflow_utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows.qdegree.tools import save_feedback, send_whatsapp_templated_message
from chat.whatsapp_providers.whatsapp_message import WhatsAppMessage
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, extract_tool_info, get_context, router, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe
from services.services.base_agent import BaseAgent
from metering.services.openmeter import OpenMeter # type: ignore


@observe()
def create_workflow(latest_survey_id):
    context = get_context()
    company_id = context.company.id
    
    llm_info_surveyor = get_active_prompt_from_langfuse(company_id, f"qdegree_{latest_survey_id}")
    survey_agent = create_agent(llm_info_surveyor, [save_feedback, send_whatsapp_templated_message])
    survey_node = functools.partial(agent_node, agent=survey_agent, name="Surveyor", llm_info=llm_info_surveyor)
    
    tool_node = ToolNode([save_feedback, send_whatsapp_templated_message])

    workflow = StateGraph(AgentState)
    workflow.add_node("Surveyor", survey_node)
    workflow.add_node("call_tool", tool_node)
    
    workflow.add_edge(START, "Surveyor")
    workflow.add_conditional_edges(
        "Surveyor",
        router,
        {"continue": "Surveyor", "call_tool": "call_tool", "__end__": END},
    )
    
    workflow.add_edge("call_tool", "Surveyor")
    return workflow.compile()


@observe()
def extract_latest_survey_id(chat_history: list) -> int:
    # adding quick solve for demo purposes will be fixed and optimised later
    context = get_context()
    pattern = r'survey_id:(\d+)'
    company_pattern = r'Start \((.*?)\)'

    company_survey_ids = {
        'tanishq': 17,
        'samsung': 18,
        'qdegrees': 19
    }

    try: 
        for message in chat_history:
            if message['role'] == 'user':
                matches = re.findall(pattern, message['content'])
                if matches:
                    return int(matches[0])
            company_matches = re.findall(company_pattern, message['content'])
            if company_matches:
                company = company_matches[0].lower()
                try:
                    return company_survey_ids[company]
                except KeyError as ke:
                    raise IncorrectSurveyError(f"Survey not found for keyword: {ke}. [company: {context.company}]")
                
        raise IncorrectSurveyError(f"No survey id provided. [company: {context.company}]")
    except IncorrectSurveyError as e:
        return f"No survey available : {e}, [company : {context.company}]"
            


def remove_final_answer(content: str) -> str:
    """
    Removes 'FINAL ANSWER' from the message content.
    """
    # Remove 'FINAL ANSWER' and any surrounding whitespace or newlines
    cleaned_content = re.sub(r'\s*FINAL ANSWER\s*', '', content, flags=re.IGNORECASE)

    # Trim any trailing whitespace or newlines
    cleaned_content = cleaned_content.rstrip()

    return cleaned_content


@observe()
def run_workflow(
    initial_message: str, 
    mobile_number: str, 
    session_id: str, 
    client_identifier: str,
    company: Company, 
    openmeter_obj: OpenMeter, 
    message_data: dict, 
    whatsapp_provider
    ) -> List[Dict]:


    # saving initial message in history
    extra_save_data = {
        'session_id': session_id if session_id else None,
        'client_identifier': client_identifier if client_identifier else None,
        'message_id': message_data.get('message_id') if message_data else None,
        'message_type': message_data.get('message_type') if message_data else None,
        'message_metadata': message_data.get('message_metadata') if message_data else None,
        'billing_session_id' : openmeter_obj.billing_session_id,
        'request_id' : openmeter_obj.request_id,
        'request_medium' : openmeter_obj.api_controller.request_medium
    }
    extra_save_data = {k: v for k, v in extra_save_data.items() if v is not None}

    reg = Registry()
    reg.set(API_MOBILE, mobile_number)

    context = WorkflowContext(
        mobile=mobile_number,
        session_id=session_id,
        company=company,
        openmeter=openmeter_obj,
        extra_save_data={
            "session_id": session_id,
            "client_identifier": client_identifier,
            "message_id": message_data.get('message_id') if message_data else None,
            'message_type': message_data.get('message_type') if message_data else None,
            'message_metadata': message_data.get('message_metadata') if message_data else None,
            'billing_session_id' : openmeter_obj.billing_session_id,
            'request_id' : openmeter_obj.request_id,
            'request_medium' : openmeter_obj.api_controller.request_medium
        }
    )
    set_context(context)


    utils.save_conversation(company, 'user', mobile_number, initial_message, extra_save_data)

    chat_history = utils.fetch_conversation(company, mobile_number, 30, False)
    latest_survey_id = extract_latest_survey_id(chat_history)
    if not latest_survey_id or not isinstance(latest_survey_id, (int)):
        return None
    chat_history_processed = utils.strucutre_conversation_langchain(chat_history)

    graph = create_workflow(latest_survey_id)
    events = graph.stream(
        {"messages": chat_history_processed},
        {"recursion_limit": 25},
    )

    ai_output = []
    for event in events:
        for node, node_data in event.items():
            messages = node_data.get('messages', [])
            for message in messages:
                if isinstance(message, AIMessage):
                    if message.content:
                        cleaned_content = remove_final_answer(message.content)
                        ai_output.append(cleaned_content)

                        extra_save_data['message_type'] = "text"

                        if whatsapp_provider and node != "supervisor":
                            wa_message = WhatsAppMessage(
                                phones = mobile_number,
                                message = cleaned_content
                            )
                            provider_response = whatsapp_provider.send_chat_bot_reply(wa_message)
                            extra_save_data['message_id'] = provider_response
                        utils.save_conversation(company, 'assistant', mobile_number, message.content, extra_save_data)
                        # print("\n ------------------------\n", ai_output)
                        # api_res = BaseAgent(company=company,
                        #                agent_slug="api_agent.get_recent_orders").invoke_agent(args={}, ai_args={})
                        # print("api_res", api_res)
            
            workflow_utils.push_llminfo_to_openmeter(node_data, openmeter_obj)

    return ai_output
