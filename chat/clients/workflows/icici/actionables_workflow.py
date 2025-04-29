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
    
    actionables_llm_info = get_active_prompt_from_langfuse(company_id, "actionables")
    actionables_agent = create_agent(actionables_llm_info)
    actionables_node = functools.partial(agent_node, agent=actionables_agent, name="actionables", llm_info=actionables_llm_info)

    workflow = StateGraph(AgentState)
    workflow.add_node("actionables", actionables_node)
    
    workflow.add_edge(START, "actionables")
    
    print("\nadded all nodes and edges\n")
    return workflow.compile()

def save_actionables(content):
    try:
        context = get_context()
        Registry().set(CURRENT_API_COMPANY, context.company)
        actionables_string = re.sub(r'```json\n|\n```', '', content)
        actionables_object = json.loads(actionables_string)
        schema_actions = utils.get_post_call_actionables_schema().value['actions']
        ai_actions = actionables_object['actions']
        updated_actions = []

        for schema_action, ai_action in zip(schema_actions, ai_actions):
            if schema_action['type'] == ai_action['type']:
                merged_action = schema_action.copy()
                merged_action['description'].update(ai_action.get('description', {}))
                updated_actions.append(merged_action)
            else:
                updated_actions.append(schema_action)


        def clean_json(data):
            if isinstance(data, dict):
                return {
                    key: clean_json(value)
                    for key, value in data.items()
                    if value is not None and clean_json(value) != {}
                }
            elif isinstance(data, list):
                return [clean_json(item) for item in data if clean_json(item) != {}]
            else:
                return data
            
        cleaned_data = clean_json(updated_actions)

        def remove_type_only_objects(data):
            return [item for item in data if len(item) > 1]
        
        cleaned_data = remove_type_only_objects(cleaned_data)
        utils.save_actionables(updated_actions, context.mobile, context.session_id)
        return cleaned_data
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        cleaned_data = {}
        return "Error processing actionables data"

@observe()
def run_workflow(initial_message: str, mobile_number: str, session_id: str, client_identifier: str,
                 company: Company, openmeter_obj: OpenMeter) -> List[Dict]:

    reg = Registry()
    reg.set(API_MOBILE, mobile_number)
    context = WorkflowContext(
        mobile=mobile_number,
        session_id=session_id,
        company=company,
        openmeter=openmeter_obj,  # open meter object
        extra_save_data={"session_id": session_id, "client_identifier": client_identifier}
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
                        cleaned_data = save_actionables(cleaned_content)
                        ai_output.append(cleaned_data)

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

    return ai_output[0]
