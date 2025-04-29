from datetime import datetime
from typing import Annotated, Dict, List
from langchain_core.tools import tool
from chat import utils
from chat.clients.workflows.agent_state import PipelineState
from chat.services.chat_history_manager.chat_message_saver import ChatMessageSaverService
from company.utils import CompanyUtils
from services.services.base_agent import BaseAgent
from basics.services.gcp_bucket_services import GCPBucketService
from langgraph.prebuilt import InjectedState
import pytz
from asgiref.sync import async_to_sync
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)

@tool
def create_support_ticket(conversation_summary:str, ticket_data:Dict, state: Annotated[dict, InjectedState]) -> str:
    """
    Creates a support ticket

    Args:
        ticket_data: a dictionary contains ticket keys and values. Example ticket_data={"ticket_title":"value", "ticket_type":"value", "contact_name":"value", "contact_email":"value", "applicant_phone_number":"value", "applicant_name": "value", "applicant_email":"value", "account_type":"value"}
        conversation_summary: summary of the conversation/chat_history
    """

    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(context_obj.company)
    communications, media_details = find_and_structure_message_history(context_obj.session_id)
    file_names = upload_files_trcapital(context_obj.company, media_details, context_obj.session_id)
    agent_phone_number = format_phone_number(context_obj.mobile) if ticket_data.get('agent_name', None) else ""
    contact_phone_number = format_phone_number(ticket_data['contact_phone_number']) if ticket_data.get('contact_phone_number', None) else format_phone_number(context_obj.mobile)
    arg_data = {
        "ticket_id": str(ticket_data.get("ticket_id", "")),
        "new_contact_name": ticket_data.get("contact_name",""),
        "contact_email": ticket_data.get("contact_email",""),
        "ticket_title": ticket_data['ticket_title'],
        "ticket_type": ticket_data['ticket_type'],
        "contact_phone_number": contact_phone_number,
        "applicant_phone_number": format_phone_number(ticket_data.get('applicant_phone_number',context_obj.mobile)),
        "applicant_name": ticket_data.get('applicant_name',""),
        "applicant_email": ticket_data.get('applicant_email',""),
        "communication_summary": conversation_summary,
        "types_of_account": ticket_data.get('account_type', ""),
        "rm_name": ticket_data.get('agent_name', ""),
        "rm_phone_number": agent_phone_number,
        "ticket_communications": communications,
        "file_names": file_names,
        "session_id": context_obj.session_id
    }
    workflow_logger.add(f"Tool: create_trcapital_support_ticket | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | Baseagent-create_support_ticket api arguments: {arg_data}")
    
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.create_support_ticket").invoke_agent(args=arg_data, ai_args={})
    workflow_logger.add(f"Tool: create_trcapital_support_ticket | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | Baseagent-create_support_ticket api response: {api_res}")
    
    ticket_data = api_res['message'].get('data',{})
    api_message = api_res['message'].get('message')
    
    ticket_id = None
    if ticket_data:
        ticket_id = ticket_data.get('ticket_id')
    
    if not ticket_id:
        workflow_logger.add(f"Tool: create_trcapital_support_ticket | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | Error: {api_res}")
        return f"Unable to process at this time please try again in some time."


    context_obj.openmeter.ingest_goal_completion(goal="Ticket Creation", reference_id=ticket_id)    
    utils.update_conversation_message_metadata(context_obj.session_id, ticket_id)

    return f"{api_message} Ticket ID is {ticket_id}, please expect a call from our customer support dept."


@tool
def create_support_ticket_dmat(conversation_summary:str, ticket_data:Dict, state: Annotated[dict, InjectedState]) -> str:
    """
    Creates a support ticket

    Args:
        ticket_data: a dictionary contains ticket keys and values. Example ticket_data={"ticket_title":"value", "ticket_type":"value", "contact_name":"value", "contact_email":"value", "applicant_phone_number":"value", "applicant_name": "value", "applicant_email":"value", "account_type":"value"}
        conversation_summary: summary of the conversation/chat_history
    """

    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(context_obj.company)
    communications, media_details = find_and_structure_message_history(context_obj.session_id)
    file_names = upload_files_trcapital(context_obj.company, media_details, context_obj.session_id)
    agent_phone_number = format_phone_number(context_obj.mobile) if ticket_data.get('agent_name', None) else ""
    contact_phone_number = format_phone_number(ticket_data['contact_phone_number']) if ticket_data.get('contact_phone_number', None) else format_phone_number(context_obj.mobile)
    arg_data = {
        "ticket_id": str(ticket_data.get("ticket_id", "")),
        "new_contact_name": ticket_data.get("contact_name",""),
        "contact_email": ticket_data.get("contact_email",""),
        "ticket_title": ticket_data['ticket_title'],
        "ticket_type": ticket_data['ticket_type'],
        "contact_phone_number": contact_phone_number,
        "applicant_phone_number": format_phone_number(ticket_data.get('applicant_phone_number', "")),
        "applicant_name": ticket_data.get('applicant_name',""),
        "applicant_email": ticket_data.get('applicant_email',""),
        "communication_summary": conversation_summary,
        "types_of_account": ticket_data.get('account_type', ""),
        "rm_name": ticket_data.get('agent_name', ""),
        "rm_phone_number": agent_phone_number,
        "ticket_communications": communications,
        "file_names": file_names,
        "session_id": context_obj.session_id
    }
    workflow_logger.add(f"Tool: create_trcapital_support_ticket | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | Baseagent-create_support_ticket api arguments: {arg_data}")
    
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.create_support_ticket").invoke_agent(args=arg_data, ai_args={})
    workflow_logger.add(f"Tool: create_trcapital_support_ticket | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | Baseagent-create_support_ticket api response: {api_res}")
    
    ticket_data = api_res['message'].get('data',{})
    api_message = api_res['message'].get('message')
    
    ticket_id = None
    if ticket_data:
        ticket_id = ticket_data.get('ticket_id')
    
    if not ticket_id:
        workflow_logger.add(f"Tool: create_trcapital_support_ticket | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | Error: {api_res}")
        error = f"Error: {api_res}"
        context_obj.openmeter.ingest_goal_failure(goal="Ticket Creation", error=error)
        return f"Unable to process at this time. Error: {error}"


    context_obj.openmeter.ingest_goal_completion(goal="Ticket Creation", reference_id=ticket_id)    
    utils.update_conversation_message_metadata(context_obj.session_id, ticket_id)

    return f"{api_message} Ticket ID is {ticket_id}, please expect a call from our customer support dept."


@tool
def find_customer_info(state: Annotated[dict, InjectedState]):
    """
    Finds information about the customer.
    """
    
    # context = get_context()
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    
    arg_data = {
        "phone_number": format_phone_number(context_obj.mobile),
    }
    workflow_logger.add(f"Tool: find_customer_info | Session: [{context_obj.session_id}] | [{context_obj.company}] | Find customer info api arguments: {arg_data}")
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.find_customer_info").invoke_agent(args=arg_data, ai_args={})
    workflow_logger.add(f"Tool: find_customer_info | Session: [{context_obj.session_id}] | [{context_obj.company}] | Find customer info api response: {api_res}")
    
    chat_saver = ChatMessageSaverService(company=context_obj.company, api_controller=context_obj.openmeter.api_controller)
        
    extra_save_data = {'message_type' : "text",'session_id' : context_obj.session_id, 'client_session_id':context_obj.extra_save_data['client_session_id'], 'client_identifier':context_obj.mobile}
    response = "customer name is Unknown"
    message = 'I am TR capital customer.'
    if api_res['message']['status_code'] == 200:
        customer_name = api_res['message'].get('name')
        
        if api_res['message']['is_agent'] == 'Yes': 
            message = f"I am TR capital agent and name is {customer_name}"
            response = f'This is an TR capital agent and name is {customer_name}'
        else : 
            message = f"I am an customer and my name is {customer_name}"        
            response = f'customer name is {customer_name}'
    
    async_to_sync(chat_saver.save_message)(company=context_obj.company,role='user',mobile_number=context_obj.mobile,message=message,extra_save_data=extra_save_data, client_identifier=context_obj.mobile)
    return response

@tool
def find_pending_tickets(state: Annotated[dict, InjectedState]):
    """
    Finds information about the pending tickets.
    """
    # context = get_context()
    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    
    arg_data = {
        "phone_number": format_phone_number(context_obj.mobile),
    }
    workflow_logger.add(f"Tool: find_pending_tickets | Session: [{context_obj.session_id}] | [{context_obj.company}] | Find pending tickets api arguments: {arg_data}")
    api_res = BaseAgent(company=context_obj.company,agent_slug="api_agent.pending_tickets").invoke_agent(args=arg_data, ai_args={})
    workflow_logger.add(f"Tool: find_pending_tickets | Session: [{context_obj.session_id}] | [{context_obj.company}] | Find pending tickets api response: {api_res}")
    
    pending_tickets = []
    for ticket in api_res['message']['tickets']:
        if ticket['ticket_status'] != 'Dropped' and ticket['ticket_status'] != 'Completed':
            pending_tickets.append(ticket)
            
    if not pending_tickets:
        return "There is no pending tickets for now."
            
    return f"pending tickets: {pending_tickets}"

def upload_files_trcapital(company, media_details, session_id):
    
    try:
        media_names = []
        gcp_bucket_service = GCPBucketService()
        for media in media_details:
            all_media = media['media'].split(',')
            counter = 1
            for _media in all_media:

                response = gcp_bucket_service.download_from_url(_media)
                
                file_extension = _media.split('.')[-1]
                now = datetime.now()
                message_id = media['message_id']
                
                media_name = f'{company.prefix}_{company.id}_{now.year}_{now.month}_{now.day}_{message_id}_{counter}.{file_extension}'
                files = {"file": (media_name, response)}

                api_res = BaseAgent(company=company,agent_slug="api_agent.upload_file").invoke_agent(args=files, ai_args={})
                media_names.append(api_res['message']['name'])
                counter += 1
                
                workflow_logger.add(f"Method: upload_files_trcapital | Session: [{session_id}] | [{company}] | File uploaded succesfully to TR capital with url: {_media}")
            
        return media_names
    except Exception as e:
        workflow_logger.add(f"Error - Method: upload_files_trcapital | Session: [{session_id}] | [{company}] | Error: {e}")
        return []

def find_and_structure_message_history(session_id: List) -> List:
    history = utils.fetch_conversation_by_session_id(session_id=session_id)
    sender_map = {
        'assistant': 'System',
        'user': 'User'
    }

    req_history = []
    media_details = []
    for item in history:
        # if 'message_id' in item and item['message_id'] is None:
        #     continue
        if item['role'] not in ["user", "assistant"]:
            continue
        created_at = item['created_at']
        dt_object = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
        dt_object = dt_object.replace(tzinfo=pytz.UTC)
        ist_timezone = pytz.timezone('Asia/Kolkata')
        ist_time = dt_object.astimezone(ist_timezone)
        formatted_time = ist_time.strftime('%Y-%m-%d %H:%M:%S')
        
        sender = sender_map.get(item['role'], item['role'])
        entry = {'sender': sender, 'message': item['message'], 'time' : formatted_time, 'message_id': str(item['id'])}
        req_history.append(entry)

        if item.get("message_metadata") and item["message_metadata"].get("media_url"):
            media = item["message_metadata"]["media_url"]
            if "ticket_id" not in item["message_metadata"]:
                media_details.append({'media': media, 'message_id': item['message_id']})

    return req_history, media_details

def format_phone_number(phone: str) -> str:
    """
    Adds '+' to the start of the phone number and '-' after country code.
    """

    phone = phone.replace('+', '').replace('-', '')
    if len(phone) > 10: phone = f'+91-{phone[2:]}'
    elif phone: phone = f'+91-{phone}'

    return phone