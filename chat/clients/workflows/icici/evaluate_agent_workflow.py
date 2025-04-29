import json
import re
from typing import Dict, List
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START
import functools
from backend.constants import API_MOBILE, CURRENT_API_COMPANY
from basics.utils import Registry
from chat import utils
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
    
    evaluate_agent_llm_info = get_active_prompt_from_langfuse(company_id, "agent_evaluate")
    evaluate_agent = create_agent(evaluate_agent_llm_info)
    evaluate_agent_node = functools.partial(agent_node, agent=evaluate_agent, name="evaluator", llm_info=evaluate_agent_llm_info)

    workflow = StateGraph(AgentState)
    workflow.add_node("evaluator", evaluate_agent_node)
    
    workflow.add_edge(START, "evaluator")
    
    print("\nadded all nodes and edges\n")
    return workflow.compile()

def save_agent_evaluation(content):
    try:
        context = get_context()
        Registry().set(CURRENT_API_COMPANY, context.company)
        evaluation_string = re.sub(r'```json\r?\n|```\r?\n?', '', content, flags=re.MULTILINE)
        evaluation_schema = utils.get_agent_performance_schema().value['evaluation']
        evaluation_object = json.loads(evaluation_string)
        ai_evaluation = evaluation_object['evaluation']

        def update_schema(schema, data):
            for key, value in schema.items():
                if isinstance(value, dict):
                    if key in data:
                        update_schema(value, data[key])
                else:
                    if key in data:
                        schema[key] = data[key]

        update_schema(evaluation_schema, ai_evaluation)
        utils.save_agent_evaluation(context.mobile,evaluation_schema)
        return evaluation_schema
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f'error evaluating agent {e}')
        return {}

def get_agent_profile_data(agent_reference_id):
    agent_data = utils.get_agent_data(agent_reference_id)
    return agent_data

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
                        ai_output.append(cleaned_content)
                        save_agent_evaluation(cleaned_content)
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