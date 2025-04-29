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
from chat.clients.workflows.common_tools import search_document_archive_for_info
from chat.workflow_utils import AgentState, create_agent, remove_final_answer, router, agent_node
from company.models import Company
from metering.services.openmeter import OpenMeter
from langfuse.decorators import observe
from chat.workflow_utils import WorkflowContext, get_context, set_context


@observe()
def create_workflow():
    context = get_context()

    researcher_llm_info = get_active_prompt_from_langfuse(context.company.id, "researcher")
    research_agent = create_agent(researcher_llm_info,[search_document_archive_for_info])
    research_node = functools.partial(agent_node, agent=research_agent, name="researcher", llm_info=researcher_llm_info)

    tool_node = ToolNode([search_document_archive_for_info])

    workflow = StateGraph(AgentState)
    workflow.add_node("researcher", research_node)
    workflow.add_node("call_tool", tool_node)

    workflow.add_edge(START, "researcher")

    workflow.add_conditional_edges(
        "researcher",
        router,
        {"continue":"researcher", "call_tool": "call_tool", "__end__": END},
    )
    workflow.add_conditional_edges(
        "call_tool",
        lambda x: x["sender"],
        {
            "researcher": "researcher"
        }
    )
    print("\nAdding all nodes and edges\n")
    return workflow.compile()


@observe()
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str, company: Company, openmeter_obj: OpenMeter) -> List[Dict]:
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

    chat_history = utils.fetch_conversation(company, mobile_number, 30, False)

    chat_history_processed = utils.strucutre_conversation_langchain(chat_history)

    graph = create_workflow()
    events = graph.stream(
        {
            "messages": chat_history_processed,
        },
        {"recursion_limit": 25},
    )

    ai_output = []
    for event in events:
        print("\nevent\n", event, "\n")
        for node, node_data in event.items():
            messages = node_data.get('messages', [])
            for message in messages:
                if isinstance(message, AIMessage):
                    if message.content:
                        cleaned_content = remove_final_answer(message.content)
                        evaluation_string = re.sub(r'```json\r?\n|```\r?\n?', '', cleaned_content, flags=re.MULTILINE)
                        ai_output.append(evaluation_string)
                        utils.save_conversation(company, 'assistant', mobile_number, message.content, extra_save_data)

            workflow_utils.push_llminfo_to_openmeter(node_data, openmeter_obj)
                    
    return ai_output[0]