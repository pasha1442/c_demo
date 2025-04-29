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
from chat.clients.workflows.geeta.tools import recommend_books, knowledge_retriver
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, create_supervisor_agent, extract_tool_info, get_context, router, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe # type: ignore
from metering.services.openmeter import OpenMeter

@observe()
def create_workflow():
    print("\ncreating agent\n")
    context = get_context()
    company_id = context.company.id
    
    members = ["catalogue_recommender", "mentor", "FINISH"]
    llm_info_supervisor = get_active_prompt_from_langfuse(company_id, "supervisor")
    supervisor_agent = create_supervisor_agent(members, llm_info_supervisor)
    supervisor_node = functools.partial(agent_node, agent=supervisor_agent, name="supervisor", llm_info=llm_info_supervisor)
    
    llm_info_mentor = get_active_prompt_from_langfuse(company_id, "mentor")
    geeta_expert_agent = create_agent(llm_info_mentor, [knowledge_retriver])
    geeta_expert_node = functools.partial(agent_node, agent=geeta_expert_agent, name="mentor", llm_info=llm_info_mentor)
    
    llm_info_recommender = get_active_prompt_from_langfuse(company_id, "catalogue_recommender")
    sales_agent = create_agent(llm_info_recommender, [recommend_books])
    catalogue_recommender = functools.partial(agent_node, agent=sales_agent, name="catalogue_recommender", llm_info=llm_info_recommender)
    
    tool_node = ToolNode([knowledge_retriver, recommend_books])
    
    workflow = StateGraph(AgentState)
    workflow.add_node("mentor", geeta_expert_node)
    workflow.add_node("call_tool", tool_node)
    workflow.add_node("catalogue_recommender", catalogue_recommender)
    workflow.add_node("supervisor", supervisor_node)
    
    workflow.add_edge(START, "supervisor")
    
    conditional_map = {k: k for k in members}
    conditional_map["FINISH"] = END
    workflow.add_conditional_edges(
        "supervisor", 
        lambda x: x["messages"][-1].content, 
        conditional_map
    )
    
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "mentor",
        router,
        {"continue": "mentor", "call_tool": "call_tool", "catalogue_recommender": "catalogue_recommender", "__end__": END},
    )
    
    workflow.add_conditional_edges(
        "catalogue_recommender",
        router,
        {"continue": "catalogue_recommender", "call_tool": "call_tool", "__end__": END},
    )

    workflow.add_conditional_edges(
        "call_tool",
        lambda x: x["sender"],
        {"mentor": "mentor", "catalogue_recommender":"catalogue_recommender"}
    )
    # workflow.add_edge("Validator",END)
    print("\nadded all nodes and edges\n")
    return workflow.compile()

@observe()  
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str, company: Company,openmeter_obj: OpenMeter) -> List[Dict]:
    #saving initial message in history
    extra_save_data = {}
    if session_id:
        extra_save_data['session_id'] = session_id
    if client_identifier:
        extra_save_data['client_identifier'] = client_identifier

    reg = Registry()
    reg.set(API_MOBILE, mobile_number)
    context = WorkflowContext(
        mobile=mobile_number,
        session_id=session_id,
        company=company,
        openmeter=openmeter_obj,
        extra_save_data={"session_id": session_id, "client_identifier": client_identifier}
    )
    set_context(context)
    utils.save_conversation(company, 'user', mobile_number, initial_message, extra_save_data)
    chat_history = utils.fetch_conversation(company, mobile_number, 20, True)
    
    chat_history_processed = utils.strucutre_conversation_langchain(chat_history)
    print("\ncompany in Geeta run_workflow: \n",Registry().get(CURRENT_API_COMPANY),"\n")

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
    ai_output = ai_output[1:]
    response = ''
    if len(ai_output) == 0:
        ai_output = "Hey, I am geeta expert. How can I help you today?"
    else:
        for message in ai_output:
            response += message+"\n"
    return response