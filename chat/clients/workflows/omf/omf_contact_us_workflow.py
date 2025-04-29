import json
from typing import Dict, List
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
import functools
from backend.constants import API_MOBILE, CURRENT_API_COMPANY
from basics.utils import Registry
from chat import utils
from chat import workflow_utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows.omf.tools import knowledge_retriver
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, extract_tool_info, get_context, router, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe # type: ignore
from metering.services.openmeter import OpenMeter

@observe()
def create_workflow():
    print("\ncreating agent\n")
    context = get_context()
    company_id = context.company.id
    
    llm_info_omf_agent = get_active_prompt_from_langfuse(company_id, "contact_us_chat")
    omf_agent = create_agent(llm_info_omf_agent, [knowledge_retriver])
    omf_agent_node = functools.partial(agent_node, agent=omf_agent, name="omf_agent", llm_info=llm_info_omf_agent)
    
    tool_node = ToolNode([knowledge_retriver])
    
    workflow = StateGraph(AgentState)
    workflow.add_node("omf_agent", omf_agent_node)
    workflow.add_node("call_tool", tool_node)
    
    workflow.add_edge(START, "omf_agent")
    workflow.add_conditional_edges(
        "omf_agent",
        router,
        {"continue": "omf_agent", "call_tool": "call_tool", "__end__": END},
    )

    workflow.add_conditional_edges(
        "call_tool",
        lambda x: x["sender"],
        {"omf_agent": "omf_agent"}
    )
    # workflow.add_edge("Validator",END)
    print("\nadded all nodes and edges\n")
    return workflow.compile()

@observe()  
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str, company: Company,openmeter_obj: OpenMeter) -> List[Dict]:
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
        openmeter=openmeter_obj,
        extra_save_data=extra_save_data
    )
    set_context(context)
    utils.save_conversation(company, 'user', mobile_number, initial_message, extra_save_data)
    chat_history = utils.fetch_conversation(company, mobile_number, 20, True)
    
    chat_history_processed = utils.strucutre_conversation_langchain(chat_history)
    # print("\ncompany in Geeta run_workflow: \n",Registry().get(CURRENT_API_COMPANY),"\n")

    # breakpoint()

    print("\n\n\nchat history sent to the chatbot",chat_history,"\n\n")
    graph = create_workflow()
    
    events = graph.stream(
        {
            "messages": chat_history_processed,
        },
        {"recursion_limit": 25},
    )
    # print(events)
    ai_output = []
    for event in events:
        print("\n",event,"\n")
        for node, node_data in event.items():
            messages = node_data.get('messages', [])
            for message in messages:
                if isinstance(message, AIMessage):
                    if message.content:
                        ai_output.append(message.content)
                        utils.save_conversation(company, 'assistant', mobile_number, message.content, extra_save_data)
                    elif message.additional_kwargs.get('tool_calls'):
                        tool_calls = message.additional_kwargs.get('tool_calls')
                        tool_info = extract_tool_info(tool_calls)
                        for name, args in tool_info:
                            extra_save_data['function_name'] = name
                            utils.save_conversation(company, 'assistant', mobile_number, json.dumps(args), extra_save_data)
                            extra_save_data['function_name'] = ""
            workflow_utils.push_llminfo_to_openmeter(node_data, openmeter_obj)

    print("\nprinting stream\n")

    for s in events:
        print(s)
        print("----")
        
    return ai_output[-1]