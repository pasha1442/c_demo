import json
import re
from typing import Dict, List
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
import functools
from backend.constants import API_MOBILE
from basics.utils import Registry
from chat import utils
from chat import workflow_utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows.common_tools import knowledge_retriver
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, get_context, remove_final_answer, router, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe
from services.services.base_agent import BaseAgent
from metering.services.openmeter import OpenMeter # type: ignore


@observe()
def create_workflow():
    context = get_context()
    company_id = context.company.id
    
    agent_assistant_llm_info = get_active_prompt_from_langfuse(company_id, "agent_assistant")
    agent_assistant_agent = create_agent(agent_assistant_llm_info, [knowledge_retriver])
    agent_assistant_node = functools.partial(agent_node, agent=agent_assistant_agent, name="assistant", llm_info=agent_assistant_llm_info)
    
    tool_node = ToolNode([knowledge_retriver])

    workflow = StateGraph(AgentState)
    workflow.add_node("assistant", agent_assistant_node)
    workflow.add_node("call_tool", tool_node)
    
    workflow.add_edge(START, "assistant")
    workflow.add_conditional_edges(
        "assistant",
        router,
        {"continue": "assistant", "call_tool": "call_tool", "__end__": END},
    )
    
    workflow.add_edge("call_tool", "assistant")
    print("\nadded all nodes and edges\n")
    return workflow.compile()


@observe()
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str,
                 company: Company, openmeter_obj: OpenMeter, conversation: str) -> List[Dict]:
    # saving initial message in history
    extra_save_data = {
            'session_id': session_id if session_id else None,
            'client_identifier': client_identifier if client_identifier else None,
            'billing_session_id' : openmeter_obj.billing_session_id,
            'request_id' : openmeter_obj.request_id,
            'request_medium' : openmeter_obj.api_controller.request_medium
    }
    reg = Registry()
    reg.set(API_MOBILE, mobile_number)
    context = WorkflowContext(
        mobile=mobile_number,
        session_id=session_id,
        company=company,
        openmeter=openmeter_obj,  # open meter object
        extra_save_data=extra_save_data
    )
    set_context(context)
    utils.save_conversation(company, 'user', mobile_number, initial_message, extra_save_data)
    chat_history = utils.fetch_conversation(company, mobile_number, 30, False)

    if conversation : 
            conversation_as_system_prompt = {
                'role' : 'system',
                'content' : f'Here is the conversation between the insurance agent and the customer for context : {conversation}'
            }
            chat_history.insert(0,conversation_as_system_prompt)

    chat_history_processed = utils.strucutre_conversation_langchain(chat_history)
    graph = create_workflow()
    
    events = graph.stream(
        {
            "messages": chat_history_processed,
            "workflow_context":context
        },
        {"recursion_limit": 25},
    )
    ai_output = []
    for event in events:
        print("\n", event, "\n")
        for node, node_data in event.items():
            messages = node_data.get('messages', [])
            for message in messages:
                if isinstance(message, AIMessage):
                    if message.content:
                        cleaned_content = remove_final_answer(message.content)
                        ai_output.append(cleaned_content)
                        utils.save_conversation(company, 'assistant', mobile_number, message.content, extra_save_data)
                        # print("\n ------------------------\n", ai_output)
                        # api_res = BaseAgent(company=company,
                        #                agent_slug="api_agent.get_recent_orders").invoke_agent(args={}, ai_args={})
                        # print("api_res", api_res)
                   # elif message.additional_kwargs.get('tool_calls'):
                    # elif message.additional_kwargs.get('tool_calls'):
                    #     tool_calls = message.additional_kwargs.get('tool_calls')
                    #     for tool_call in tool_calls:
                    #         name = tool_call['function']['name']
                    #         args = json.loads(tool_call['function']['arguments'])
                    #         tool_call_id = tool_call['id']
                    #         args['tool_call_id'] = tool_call_id

                    #         extra_save_data['function_name'] = name
                    #         utils.save_conversation(company, 'function', mobile_number, json.dumps(args), extra_save_data)
                    #         extra_save_data['function_name'] = ""
            workflow_utils.push_llminfo_to_openmeter(node_data, openmeter_obj)

    print("\nprinting stream\n")

    return ai_output
