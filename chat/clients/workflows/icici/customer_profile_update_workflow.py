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
    
    profile_updater_llm_info = get_active_prompt_from_langfuse(company_id, "customer_profile_update")
    profile_updater_agent = create_agent(profile_updater_llm_info)
    profile_updater_node = functools.partial(agent_node, agent=profile_updater_agent, name="profileupdater", llm_info=profile_updater_llm_info)

    workflow = StateGraph(AgentState)
    workflow.add_node("profileupdater", profile_updater_node)
    
    workflow.add_edge(START, "profileupdater")
    
    print("\nadded all nodes and edges\n")
    return workflow.compile()


def save_customer_profile(content):
    context = get_context()
    Registry().set(CURRENT_API_COMPANY, context.company)
    
    profile_data_string = re.sub(r'```json\n|\n```', '',content)
    profile_schema = utils.get_customer_profile_schema().value

    def generate_delta(original_profile, new_profile):
        delta = {}
        def _generate_delta(original, new, path=""):
            for key, value in new.items():
                if key not in original or original[key] != value:
                    if path:  # Handle nested paths
                        current_path = path + "." + key 
                    else:
                        current_path = key 

                    if isinstance(value, dict):
                        _generate_delta(original.get(key, {}), value, current_path)
                    else:
                        *parent_path, last_key = current_path.split(".")
                        parent_dict = delta
                        
                        for part in parent_path:
                            parent_dict.setdefault(part, {})
                            parent_dict = parent_dict[part]
                        
                        parent_dict[last_key] = value

        _generate_delta(original_profile, new_profile)
        return {"customer_profile_attributes": delta}
    
    def update_profile(schema, data, path=""):
        for schema_key, schema_value in schema.items():
            current_path = f"{path}.{schema_key}" if path else schema_key
            data_key = next((k for k in data.keys() if k.lower() == schema_key.lower()), None)
            
            if data_key is None:
                print(f"No matching key found for {current_path}")
                continue
            
            if isinstance(schema_value, dict):
                if isinstance(data[data_key], dict):
                    update_profile(schema_value, data[data_key], current_path)
                else:
                    print(f"Mismatch at {current_path}: schema expects dict, got {type(data[data_key])}")
            elif data[data_key] is not None:
                print(f"Updating {current_path}: {schema[schema_key]} -> {data[data_key]}")
                schema[schema_key] = data[data_key]
            else:
                print(f"Skipping {current_path}: value is None")
    try:
        profile_data = json.loads(profile_data_string)
        existing_profile_data = utils.get_customer_profile_temp(context.mobile)
        if existing_profile_data:
            delta = generate_delta(
                existing_profile_data['customer_profile_attributes'],  # type: ignore
                profile_data['customer_profile_attributes']
            )
        update_profile(profile_schema['customer_profile_attributes'], profile_data['customer_profile_attributes'])
        if not existing_profile_data:
            delta = profile_schema
        utils.save_customer_profile_temp(profile_schema, context.mobile)
        response_data = {
            "profile_data": profile_schema,
            "delta": delta
        }
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error processing profile data: {e}")
        response_data = {
            "profile_data": {},
            "delta": {}
        }

    return response_data

def save_customer_profile_manual(profile_data, mobile_number):
    try:
        profile_data = json.loads(profile_data)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
            return {f"JSON error : {e}"}
    profile_schema = utils.get_customer_profile_schema().value
    def update_profile(schema, data, path=""):
        for schema_key, schema_value in schema.items():
            current_path = f"{path}.{schema_key}" if path else schema_key
            data_key = next((k for k in data.keys() if k.lower() == schema_key.lower()), None)
            
            if data_key is None:
                print(f"No matching key found for {current_path}")
                continue
            
            if isinstance(schema_value, dict):
                if isinstance(data[data_key], dict):
                    update_profile(schema_value, data[data_key], current_path)
                else:
                    print(f"Mismatch at {current_path}: schema expects dict, got {type(data[data_key])}")
            elif data[data_key] is not None:
                print(f"Updating {current_path}: {schema[schema_key]} -> {data[data_key]}")
                schema[schema_key] = data[data_key]
            else:
                print(f"Skipping {current_path}: value is None")
    try: 
        update_profile(profile_schema['customer_profile_attributes'], profile_data['customer_profile_attributes'])
        utils.save_customer_profile_temp(profile_schema, mobile_number)
        return {"modified"}
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return {"failed"}

def get_customer_profile(mobile_number):
    profile_data = utils.get_customer_profile_temp(mobile_number)
    return profile_data

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
                        updated_profile_data = save_customer_profile(cleaned_content)
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

    return updated_profile_data