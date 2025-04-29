from typing import List, Optional
from langchain_core.tools import tool
from chat import utils
from chat.clients.workflows.agent_state import PipelineState
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from chat.workflow_utils import get_context
from company.models import CompanyEntity
from company.utils import CompanyUtils
from services.services.base_agent import BaseAgent
from langgraph.prebuilt import InjectedState
from typing import Annotated

from chat.services.chat_history_manager.chat_message_saver import ChatMessageSaverService
from asgiref.sync import async_to_sync
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)

@tool(return_direct=True)
def check_badho_ongoing_incidents(state: Annotated[dict, InjectedState]) -> List:
    """
    Checks if any ongoing incidents are going on in the website
    """
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(company=context_obj.company)
    extra_save_data = {
        'function_name' : 'check_badho_ongoing_incidents',
        'session_id' : context_obj.session_id
    }
    all_save_data = context_obj.extra_save_data | extra_save_data
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.get_ongoing_incidents").invoke_agent(args={}, ai_args={})
    workflow_logger.add(f"[company : {context_obj.company}] [session_id : {context_obj.session_id}] check_ongoing_incidents api response: {api_res}")
    ongoing_incidents = api_res.get('data',{}).get('incidents_incident','No incidents found')

    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)
    async_to_sync(chat_saver.save_message)(
        company=context_obj.company,
        role='function',
        mobile_number=context_obj.mobile,
        message=f"ongoing incidents: {ongoing_incidents}",
        extra_save_data=all_save_data,
        client_identifier=context_obj.extra_save_data['client_identifier']
    )
    return ongoing_incidents

# @tool
# def create_badho_support_ticket(form_id: str, form_label: str, form_config, state: Annotated[dict, InjectedState]) -> str:
#     """
#     Creates a support ticket

#     Args:
#         form_id : if of the form
#         form_label : label of the form
#         form_config : the config of the form with filled information (needs to be exactly same as provided by get_information_config_by_ticket_type tool)
#     """

#     context = state['workflow_context']
#     CompanyUtils.set_company_registry(company=context.company)
#     extra_save_data = {
#         'function_name' : 'create_badho_support_ticket',
#         'session_id' : context.session_id
#     }
#     all_save_data = context.extra_save_data | extra_save_data
#     arg_data = {
#         'variables' : {
#             'object' : {
#                 "formId": form_id,
#                 "formData": {
#                     "label": form_label,
#                     "config" : form_config
#                 },
#                 "modifiedById": "",
#                 "modifiedByRole": "whatsapp",
#                 "normalizedFormData": {}
#             }
#         }
#     }
        
#     ticket_res = BaseAgent(company=context.company,agent_slug="api_agent.create_form_entry").invoke_agent(args=arg_data, ai_args={})
#     logger.info(f"[company : {context.company}] [session_id : {context.session_id}] create_support_ticket api response: {ticket_res}")

#     ticket_id = ticket_res.get('data',{}).get('insert_forms_formEntry_one',{}).get('id', None)
#     chat_saver = ChatMessageSaverService(company=context.company, api_controller=context.openmeter.api_controller)

#     if not ticket_id:

#         async_to_sync(chat_saver.save_message)(
#             company=context.company,
#             role='function',
#             mobile_number=context.mobile,
#             message="Failed to create ticket, try again later",
#             extra_save_data=all_save_data,
#             client_identifier=context.extra_save_data['client_identifier']
#         )
#         return f"We have issues creating tickets right now, please try again later"

#     async_to_sync(chat_saver.save_message)(
#         company=context.company,
#         role='function',
#         mobile_number=context.mobile,
#         message=f"created ticket: {ticket_id}",
#         extra_save_data=all_save_data,
#         client_identifier=context.extra_save_data['client_identifier']
#     )
#     return f"Succesfully generated support ticket with id {ticket_id}, please expect a call from our customer support dept."

def extract_user_type_from_api(data):
    buyers = {user['id']: user for user in data['data'].get('users_buyer', [])}
    sellers = {user['id']: user for user in data['data'].get('users_seller', [])}
    employees = {user['id']: user for user in data['data'].get('employeeBase_employee', [])}

    user_types = set()
    if buyers:
        user_types.add('buyer')
    if sellers:
        user_types.add('seller')
    if employees:
        user_types.add('employee')

    has_multiple_types = len(user_types) > 1
    
    return ', '.join(sorted(user_types)), has_multiple_types

@tool
def find_badho_customer_user_type(state: Annotated[dict, InjectedState]):
    """
    Finds out the user type of the customer. (buyer|seller|employee)
    """
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(company=context_obj.company)
    extra_save_data = {
        'function_name' : 'find_badho_customer_user_type',
        'session_id' : context_obj.session_id
    }
    
    phone = remove_country_code(context_obj.mobile)
    all_save_data = context_obj.extra_save_data | extra_save_data
    arg_data = {
        'variables' : {
            'phone' : phone
        }
    }
        
    customer_info = BaseAgent(company=context_obj.company,agent_slug="api_agent.find_customer_by_phone").invoke_agent(args=arg_data, ai_args={})
    workflow_logger.add(f"[company : {context_obj.company}] [session_id : {context_obj.session_id}] find_customer_info api response: {customer_info}")
    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)

    user_type, multiple_accounts = extract_user_type_from_api(customer_info)
    if multiple_accounts:
        message = f"User has multiple accounts {user_type}, ask them which account they would like to access right now."
        async_to_sync(chat_saver.save_message)(
            company=context_obj.company,
            role='function',
            mobile_number=context_obj.mobile,
            message=f"{message}",
            extra_save_data=all_save_data,
            client_identifier=context_obj.extra_save_data['client_identifier']
        )
        return message
    elif user_type and not multiple_accounts:
        return f"User is a {user_type}, proceed to find their info"
    else:
        return "No such customer registered with Badho, please use your registered phone number"

@tool
def find_badho_customer_info(user_type: str, state: Annotated[dict, InjectedState] = []):
    """
    Finds information about the customer.
    user_type: user type of the customer (buyer or seller or employee)
            If the customer has multiple types, donot assume user type. always ask the customer which account they would
            like to access
    """
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(company=context_obj.company)
    extra_save_data = {
        'function_name' : 'find_badho_customer_info',
        'session_id' : context_obj.session_id
    }
    phone = remove_country_code(context_obj.mobile)
    all_save_data = context_obj.extra_save_data | extra_save_data
    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)

    arg_data = {
        'appName' : user_type,
        'appPhoneNumber' : phone
    }

    customer_data = BaseAgent(company=context_obj.company,agent_slug="api_agent.fetch_access_token").invoke_agent(args=arg_data, ai_args={})
    required_customer_data  = {
        'access_token' : customer_data['accessToken'],
        'user_name' : customer_data['userDetails']['name'],
        'user_type' : user_type
    }
    async_to_sync(chat_saver.save_message)(
        company=context_obj.company,
        role='function',
        mobile_number=context_obj.mobile,
        message=f"customer details: {required_customer_data}",
        extra_save_data=all_save_data,
        client_identifier=context_obj.extra_save_data['client_identifier']
    )
    cache_service = InMemoryChatHistoryService(company= context_obj.company, api_controller=context_obj.openmeter.api_controller)
    cache_data = cache_service.save_client_metadata(company = context_obj.company, client_identifier=context_obj.extra_save_data['client_identifier'], data=required_customer_data)
    return required_customer_data
        

@tool
def get_badho_information_config_by_ticket_type(formid: str, state: Annotated[dict, InjectedState]):
    """
    Finds configuration of the form using its formId

    Args:
        formid: formId of the form.
        example : REPORT_A_PROBLEM | INCORRECT_PRICE_ISSUE
    """
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(company=context_obj.company)
    extra_save_data = {
        'function_name' : 'get_badho_information_config_by_ticket_type',
        'session_id' : context_obj.session_id
    }
    all_save_data = context_obj.extra_save_data | extra_save_data
    arg_data = {
        'variables' : {
            'formid' : formid
        }
    }
        
    form_config = BaseAgent(company=context_obj.company,agent_slug="api_agent.find_config_by_formid").invoke_agent(args=arg_data, ai_args={})
    workflow_logger.add(f"[company : {context_obj.company}] [session_id : {context_obj.session_id}] get_information_config_by_ticket_type api response: {form_config}")

    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)
    async_to_sync(chat_saver.save_message)(
        company=context_obj.company,
        role='function',
        mobile_number=context_obj.mobile,
        message=f"Config of {formid} form is : {form_config}",
        extra_save_data=all_save_data,
        client_identifier=context_obj.extra_save_data['client_identifier']
    )
    return f"Config of {formid} form is : {form_config}, use this exact config when creating the ticket."


@tool
def get_badho_ticket_categories_for_user_type(user_type: str, state: Annotated[dict, InjectedState]):
    """
    Finds all ticket categories for the current user type

    Args:
        user_type: type of user (buyer|seller|employee)
    """
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(company=context_obj.company)
    
    form_user_type_mapping = {
        'buyer' : 'buyerForms',
        'seller' : 'sellerForms',
        'employee' : 'employeeForms'
    }
    all_forms = CompanyEntity.objects.get(reference_id="badho_form_ids", type="ticket_types")
    required_forms = all_forms.data.get('data',{}).get(form_user_type_mapping[user_type],{})
    workflow_logger.add(f"[company : {context_obj.company}] [session_id : {context_obj.session_id}] get_ticket_categories_for_user_type : {user_type} api response: {all_forms}")

    return f"categorize customer issue into one of : {required_forms}"

def remove_country_code(phone_number: str) -> str:
    if phone_number.startswith('91'):
        return phone_number[2:]
    return phone_number


@tool()
def fetch_tools(query : str = "", tool_label: str = "", state: Annotated[dict, InjectedState] = "") -> List:
    """
    Fetches available tools for the current query.

    Args:
        query (str): The query string.
        tool_label (str, optional): Label of the tool to fetch. 
            Defaults to an empty string, which means no specific tool label is required.
    
    Returns:
        List: List of fetched tools.
    """

    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(company=context_obj.company)
    extra_save_data = {
        'function_name' : 'fetch_tools',
        'session_id' : context_obj.session_id
    }
    all_save_data = context_obj.extra_save_data | extra_save_data
    cache_service = InMemoryChatHistoryService(company= context_obj.company, api_controller=context_obj.openmeter.api_controller)

    client_metadata = cache_service.get_client_metadata(company=context_obj.company, client_identifier=context_obj.extra_save_data['client_identifier'])
    if tool_label:
            arg_data = {
                'variables' : {
                    'params' :  {
                        'label' : tool_label,
                    }
                }
            }
    else:
        arg_data = {
            'variables' : {
                'params' :  {
                    'userQuery' : client_metadata['user_type'] + query,
                }
            }
        }
    
    custom_headers = {
        "authorization" : client_metadata['access_token'],
        "authorization-type" : client_metadata['user_type'],
        "accept": "application/json",
        "content-type": "application/json",
    }
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.fetch_tools").invoke_agent(args=arg_data, ai_args={}, custom_headers=custom_headers)
    workflow_logger.add(f"[company : {context_obj.company}] [session_id : {context_obj.session_id}] arg_data : {arg_data} custom_headers : {custom_headers} fetch_tools api response: {api_res}")

    tools = api_res.get('data',{}).get('embeddings_fetch_llm_tools_new','No tools found, try to rephrase the query and try again immediately without telling the customer.')

    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)
    async_to_sync(chat_saver.save_message)(
        company=context_obj.company,
        role='function',
        mobile_number=context_obj.mobile,
        message=f"available tools: {tools}",
        extra_save_data=all_save_data,
        client_identifier=context_obj.extra_save_data['client_identifier']
    )
    return tools


@tool
def run_tools(tool_id: str, params, state: Annotated[dict, InjectedState]):
    """
    Runs the tool to get response

    tool_id : unique tool id
    params : json params required to run the tool, pass {} if none required
    """

    if not params:
        params = {}
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state) 
    CompanyUtils.set_company_registry(company=context_obj.company)
    extra_save_data = {
        'function_name' : 'run_tools',
        'session_id' : context_obj.session_id
    }
    all_save_data = context_obj.extra_save_data | extra_save_data

    arg_data = {
        'variables' : {
            'params' :  params,
            'llmToolId' : tool_id,
            'runId': "12323324" # random run id
        }
    }
    cache_service = InMemoryChatHistoryService(company= context_obj.company, api_controller=context_obj.openmeter.api_controller)

    client_metadata = cache_service.get_client_metadata(company=context_obj.company, client_identifier=context_obj.extra_save_data['client_identifier'])
    custom_headers = {
        "authorization" : client_metadata['access_token'],
        "authorization-type" : client_metadata['user_type'],
        "accept": "application/json",
        "content-type": "application/json",
    }
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.run_tools").invoke_agent(args=arg_data, ai_args={}, custom_headers=custom_headers)
    workflow_logger.add(f"[company : {context_obj.company}] [session_id : {context_obj.session_id}] run_tools api response: {api_res}")
    tool_response = api_res.get('data',{}).get('embeddings_run_llm_tool','Tools was not able to run')

    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)
    async_to_sync(chat_saver.save_message)(
        company=context_obj.company,
        role='function',
        mobile_number=context_obj.mobile,
        message=f"response from tool: {tool_response}",
        extra_save_data=all_save_data,
        client_identifier=context_obj.extra_save_data['client_identifier']
    )
    return tool_response