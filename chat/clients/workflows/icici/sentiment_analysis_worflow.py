import re
from typing import Dict, List
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START
import functools
from backend.constants import API_MOBILE
from basics.utils import Registry
from chat import workflow_utils
from chat.assistants import get_active_prompt_from_langfuse
from chat.workflow_utils import AgentState, WorkflowContext, create_agent, get_context, remove_final_answer, agent_node, set_context
from company.models import Company
from langfuse.decorators import observe
from services.services.base_agent import BaseAgent
from metering.services.openmeter import OpenMeter # type: ignore


@observe()
def create_workflow():
    context = get_context()
    company_id = context.company.id
    
    sentiment_analysis_llm_info = get_active_prompt_from_langfuse(company_id, "sentiment_analysis")
    sentiment_analysis_agent = create_agent(sentiment_analysis_llm_info)
    sentiment_analysis_node = functools.partial(agent_node, agent=sentiment_analysis_agent, name="sentimentanalyzer", llm_info=sentiment_analysis_llm_info)

    workflow = StateGraph(AgentState)
    workflow.add_node("sentimentanalyzer", sentiment_analysis_node)
    
    workflow.add_edge(START, "sentimentanalyzer")
    
    print("\nadded all nodes and edges\n")
    return workflow.compile()


@observe()
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str,
                 company: Company, openmeter_obj: OpenMeter) -> List[Dict]:

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
    graph = create_workflow()
    
    events = graph.stream(
        {
            "messages": [HumanMessage(content=initial_message)],
        },
        {"recursion_limit": 10},
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
                        cleaned_string = re.sub(r'```json\r?\n|```\r?\n?', '', cleaned_content, flags=re.MULTILINE)
                        ai_output.append(cleaned_string)
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