from typing import Dict, List
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
import functools
from chat import utils
from chat import workflow_utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows.badho.tools import check_ongoing_incidents, create_support_ticket, find_customer_info
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, get_context, remove_final_answer, router, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe
from metering.services.openmeter import OpenMeter


@observe()
def create_workflow():
    print("\ncreating agent\n")
    context = get_context()
    company_id = context.company.id
    
    llm_info_cs = get_active_prompt_from_langfuse(company_id, "customer_support")
    cs_agent = create_agent(llm_info_cs, [check_ongoing_incidents, create_support_ticket, find_customer_info])
    cs_node = functools.partial(agent_node, agent=cs_agent, name="customer_support", llm_info=llm_info_cs)
    
    tool_node = ToolNode([check_ongoing_incidents, create_support_ticket, find_customer_info])

    workflow = StateGraph(AgentState)
    workflow.add_node("customer_support", cs_node)
    workflow.add_node("call_tool", tool_node)
    
    workflow.add_edge(START, "customer_support")
    workflow.add_conditional_edges(
        "customer_support",
        router,
        {"continue": "customer_support", "call_tool": "call_tool", "__end__": END},
    )
    
    workflow.add_edge("call_tool", "customer_support")
    print("\nadded all nodes and edges\n")
    return workflow.compile()


@observe()
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str,
                 company: Company, openmeter_obj: OpenMeter) -> List[Dict]:
    
    user_info = f"Customer phone number : {mobile_number} "
    initial_message = user_info + initial_message
    # saving initial message in history
    extra_save_data = {}
    if session_id:
        extra_save_data['session_id'] = session_id
    if client_identifier:
        extra_save_data['client_identifier'] = client_identifier

    context = WorkflowContext(
        mobile=mobile_number,
        session_id=session_id,
        company=company,
        openmeter=openmeter_obj,  # open meter object
        extra_save_data={"session_id": session_id, "client_identifier": client_identifier}
    )
    set_context(context)
    utils.save_conversation(company, 'user', mobile_number, initial_message, extra_save_data)
    chat_history = utils.fetch_conversation(company, mobile_number, 30, True)
    print("\chat history\n",chat_history,"\n\n")

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
        print("\n", event, "\n")
        for node, node_data in event.items():
            messages = node_data.get('messages', [])
            for message in messages:
                if isinstance(message, AIMessage):
                    if message.content:
                        cleaned_content = remove_final_answer(message.content)
                        ai_output.append(cleaned_content)
                        utils.save_conversation(company, 'assistant', mobile_number, message.content, extra_save_data)
            workflow_utils.push_llminfo_to_openmeter(node_data, openmeter_obj)

    return ai_output
