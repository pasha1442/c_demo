from typing import Dict, List
from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
import functools
from chat import utils
from chat import workflow_utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows.badho.tools import check_badho_ongoing_incidents, create_badho_support_ticket, find_badho_customer_info, get_badho_information_config_by_ticket_type, get_badho_ticket_categories_for_user_type 
from chat.whatsapp_providers.whatsapp_message import WhatsAppMessage
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, create_supervisor_agent, get_context, remove_final_answer, router, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe
from metering.services.openmeter import OpenMeter


@observe()
def create_workflow():
    context = get_context()
    company_id = context.company.id
    
    llm_info_supervisor = get_active_prompt_from_langfuse(company_id, "supervisor")
    llm_info_cif = get_active_prompt_from_langfuse(company_id, "customer_information_finder")
    llm_info_ticket_creator = get_active_prompt_from_langfuse(company_id, "support_ticket_creator")
    llm_info_ongoing_incident_checker = get_active_prompt_from_langfuse(company_id, "ongoing_incident_checker")

    members = ["customer_finder", "ticket_creator", "ongoing_incident_checker", "FINISH"]

    supervisor_agent = create_supervisor_agent(members, llm_info_supervisor)
    supervisor_node = functools.partial(agent_node, agent=supervisor_agent, name="supervisor", llm_info=llm_info_supervisor)

    cif_agent = create_agent(llm_info_cif, [find_badho_customer_info])
    cif_node = functools.partial(agent_node, agent=cif_agent, name="customer_finder", llm_info=llm_info_cif)

    ticketing_agent = create_agent(llm_info_ticket_creator, [create_badho_support_ticket, get_badho_information_config_by_ticket_type, get_badho_ticket_categories_for_user_type])
    ticketing_node = functools.partial(agent_node, agent=ticketing_agent, name="ticket_creator", llm_info=llm_info_ticket_creator)

    ongoing_incidents_agent = create_agent(llm_info_ongoing_incident_checker, [check_badho_ongoing_incidents])
    ongoing_incidents_node = functools.partial(agent_node, agent=ongoing_incidents_agent, name="ongoing_incident_checker", llm_info=llm_info_ongoing_incident_checker)

    tool_node = ToolNode([check_badho_ongoing_incidents, create_badho_support_ticket, find_badho_customer_info, get_badho_information_config_by_ticket_type, get_badho_ticket_categories_for_user_type])

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("customer_finder", cif_node)
    workflow.add_node("ticket_creator", ticketing_node)
    workflow.add_node("ongoing_incident_checker", ongoing_incidents_node)
    workflow.add_node("call_tool", tool_node)
    
    workflow.add_edge(START, "supervisor")

    conditional_map = {k: k for k in members}
    conditional_map["FINISH"] = END

    workflow.add_conditional_edges(
        "supervisor", 
        lambda x: x["messages"][-1].content, 
        conditional_map
    )

    workflow.add_conditional_edges(
        "customer_finder",
        router,
        {"continue": "ticket_creator", "call_tool": "call_tool", "__end__": 'ticket_creator'},
    )

    workflow.add_conditional_edges(
        "ticket_creator",
        router,
        {"continue": "ticket_creator", "call_tool": "call_tool", "__end__": END},
    )

    workflow.add_conditional_edges(
        "ongoing_incident_checker",
        router,
        {"continue": "ticket_creator", "call_tool": "call_tool", "__end__": "ticket_creator"},
    )

    workflow.add_conditional_edges(
        "call_tool",
        lambda x: x["sender"],
        {"customer_finder": "ticket_creator", "ticket_creator":"ticket_creator", "ongoing_incident_checker":"ticket_creator"}
    )

    return workflow.compile()


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
    

    # Prepare extra data for saving conversation
    extra_save_data = {
        'session_id': session_id if session_id else None,
        'client_identifier': client_identifier if client_identifier else None,
        'message_id': message_data.get('message_id') if message_data else None,
        'message_type': message_data.get('message_type') if message_data else None,
        'message_metadata': message_data.get('message_metadata') if message_data else None
    }
    extra_save_data = {k: v for k, v in extra_save_data.items() if v is not None}

    context = WorkflowContext(
        mobile=mobile_number,
        session_id=session_id,
        company=company,
        openmeter=openmeter_obj,
        extra_save_data={
            "session_id": session_id,
            "client_identifier": client_identifier,
            "message_data": message_data
        }
    )
    set_context(context)

    utils.save_conversation(company, 'user', mobile_number, initial_message, extra_save_data)

    chat_history = utils.fetch_conversation(company, mobile_number, 30, True)
    chat_history_processed = utils.strucutre_conversation_langchain(chat_history)

    graph = create_workflow()
    events = graph.stream(
        {"messages": chat_history_processed},
        {"recursion_limit": 25},
    )


    ai_output = []
    for event in events:
        for node, node_data in event.items():
            messages = node_data.get('messages', [])
            for message in messages:
                if isinstance(message, AIMessage) and message.content:
                    cleaned_content = remove_final_answer(message.content)
                    ai_output.append(cleaned_content)

                    extra_save_data = {
                        'message_type' : "text",
                        'session_id' : session_id
                    }
                    
                    if whatsapp_provider and node != "supervisor":
                        wa_message = WhatsAppMessage(
                            phones = mobile_number,
                            message = cleaned_content
                        )
                        provider_response = whatsapp_provider.send_chat_bot_reply(wa_message)
                        extra_save_data['message_id'] = provider_response
                    
                    utils.save_conversation(company, 'assistant', mobile_number, message.content, extra_save_data)
            workflow_utils.push_llminfo_to_openmeter(node_data, openmeter_obj)

    return ai_output[1:]