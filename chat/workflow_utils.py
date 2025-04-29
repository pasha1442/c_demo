import asyncio
import contextvars
from dataclasses import dataclass
import json
import re
import time

import requests
from backend.services.celery_service import CeleryService
from chat.assistants import get_active_prompt_from_langfuse
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, ToolMessage, BaseMessage
from langchain_openai import ChatOpenAI
from typing import Annotated, Dict, List, Tuple, TypedDict, Sequence, Literal
import operator
from langfuse.decorators import observe, langfuse_context
from pydantic import BaseModel
# from chat.utils import SafeResponseCallback, input_safety_check, SafeInputCallback
from chat.models import Conversations
from chat.services.kafka_workflow_response_handler import KafkaWorkflowResponseHandler, WahaMessageState
from chat.workflow_context import WorkflowState
from company.models import Company
from company.utils import CompanyUtils
from metering.services.openmeter import OpenMeter
from asgiref.sync import sync_to_async
from backend.logger import Logger
workflow_logger = Logger(Logger.WORKFLOW_LOG)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    sender: str
    workflow_context: Annotated[WorkflowState, lambda workflow_context1, workflow_context2: workflow_context1]
    llm_info: dict
    


@dataclass
class WorkflowContext:
    mobile: str
    session_id: str
    company: Company
    openmeter:OpenMeter
    extra_save_data: Dict[str, str]

workflow_context = contextvars.ContextVar('workflow_context')

def set_context(context: WorkflowContext):
    workflow_context.set(context)

def get_context() -> WorkflowContext:
    return workflow_context.get()
    
@observe()
def agent_node(state: AgentState, agent, name: str, llm_info: dict) -> Dict:
    input_message = state["messages"][-1].content
    # if input_message and input_safety_check(input_message) == False:
    #     print(f"Unsafe Input : {input_message}")
    #     return {
    #         "messages": [AIMessage(content="Inappropriate content found. Cannot proceed with the request!", name=name)],
    #         "sender" : name
    #     }
    langfuse_handler = langfuse_context.get_current_langchain_handler()
    # get_safe_response = SafeResponseCallback()
    # result = agent.invoke(state, config={"callbacks": [langfuse_handler, get_safe_response]})

    result = agent.invoke(state, config={"callbacks": [langfuse_handler]})

    if 'tool_calls' in result.additional_kwargs:
        for tool in result.additional_kwargs['tool_calls']:
            if tool['function']['name'] == 'knowledge_retriver':
                arguments = json.loads(tool['function']['arguments'])
                arguments['data_source'] = llm_info["data_source"]
                tool['function']['arguments'] = json.dumps(arguments)
        
        for tool in result.tool_calls:
            if tool['name'] == 'knowledge_retriver':
                tool['args']['data_source'] =  llm_info["data_source"]
    
    if isinstance(result, ToolMessage):
        return {"messages": [result], "sender": name, "llm_info": llm_info}
    
    return {
        "messages": [AIMessage(**result.dict(exclude={"type", "name"}), name=name)],
        "sender": name,
        "llm_info": llm_info
    }

@observe()
def create_supervisor_agent(members, llm_info):
    system_prompt = llm_info["system_prompt"]
    llm = ChatOpenAI(model=llm_info['model'])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {members}",
            ),
        ]
    ).partial(members=", ".join(members))
    
    return prompt | llm

@observe()
def create_agent(llm_info, tools=None):
    """Create an agent."""
    system_prompt = llm_info["system_prompt"]
    llm = ChatOpenAI(model=llm_info['model'])
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "{system_prompt}\nYou have access to the following tools: {tool_names}."
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    prompt = prompt.partial(system_prompt=system_prompt)
    
    if tools:
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        return prompt | llm.bind_tools(tools)
    
    prompt = prompt.partial(tool_names="[]")
    return prompt | llm

@observe()
def router(state: AgentState) -> Literal["call_tool", "__end__", "continue"]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "call_tool"
    
    if isinstance(last_message, AIMessage):
        # Check for "FINAL ANSWER" in content
        if "FINAL ANSWER" in last_message.content:
            return "__end__"
        if "CATALOGUE RECOMMENDER" in last_message.content:
            return "catalogue_recommender"
        # Check for finish_reason "stop"
        response_metadata = last_message.response_metadata
        if response_metadata and response_metadata.get('finish_reason') == 'stop':
            return "__end__"
        
    return "continue"


@observe()
def extract_tool_info(tool_calls: List[Dict]) -> List[Tuple[str, Dict]]:
    """
    Extract name and arguments from tool calls.
    """
    tool_info = []
    for tool_call in tool_calls:
        name = tool_call.get('function', {}).get('name', '')
        args_str = tool_call.get('function', {}).get('arguments', '{}')
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}
        tool_info.append((name, args))
    
    return tool_info
    
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
def push_llminfo_to_openmeter(node_data, openmeter_obj):
    if node_data.get('messages', {}):
        om_arg = {}
        messages = node_data.get('messages', [])
        llm_info = node_data.get('llm_info', [])
        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.usage_metadata:
                    usage_data = msg.usage_metadata
                    om_arg["total_token"] = usage_data.get("total_tokens", "")
                    om_arg["input_token"] = usage_data.get("input_tokens", "")
                    om_arg["output_token"] = usage_data.get("output_tokens", "")

        if llm_info:
            om_arg["llm"] = llm_info.get("llm", "")
            om_arg["model"] = llm_info.get("model", "")
            om_arg["agent"] = llm_info.get("agent", "")
            om_arg["data_source"] = llm_info.get("data_source", "")
        if om_arg:
            openmeter_obj.ingest_llm_call(args=om_arg)
            
            

async def push_waha_message_to_queue(company, session_id, mobile_number, ai_message, waha_session):
    workflow_logger.add("push message to waha")
    #send seen message
    @sync_to_async
    def get_session_messages(session_id, company_id):
        CompanyUtils.set_company_registry(company=company)
        return Conversations.objects.filter(session_id=session_id, company_id=company_id).values_list('role', 'message_id')
    
    @sync_to_async
    def push_message(message):
        KafkaWorkflowResponseHandler().push_waha_message_to_queue(waha_message=message)
    
    session_messages = await get_session_messages(session_id, company.id)
    async for message in session_messages:
        if message[0] == 'assistant' or message[0] == 'function': break
        waha_seen_message = WahaMessageState(type='seen_message', mobile_number=mobile_number, message_id=message[1], waha_session=waha_session)
        await push_message(waha_seen_message)
        # send_seen_message_to_waha(mobile_number, message[1], waha_session)
    
    workflow_logger.add("push seen message to waha")
    
    #send start typing
    waha_start_typing_message = WahaMessageState(type='start_typing', mobile_number=mobile_number, waha_session=waha_session)
    await push_message(waha_start_typing_message)
    # send_typing_start_to_waha(mobile_number, waha_session)
    task_name = "send_to_waha_"+str(time.time())
    
    workflow_logger.add("push typing start message to waha")
    
    #send text message
    time_delay = len(ai_message.split(" "))/2
    celery_obj = CeleryService()
    celery_obj.schedule_task(task_name=task_name, countdown=time_delay, args=("text_message", mobile_number, ai_message, waha_session), kwargs={"func_name": "CeleryTools.send_message_to_waha_queue"})
    # await push_message(waha_message)
    
    workflow_logger.add("pushed message to waha.........")
    