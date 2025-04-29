import asyncio
import json
from langchain_core.messages import AIMessage
from chat import utils
from chat.clients.workflows.workflow_factory import WorkflowFactory
from chat.constants import IN_MEMORY_CHAT_HISTORY_MESSAGE_LIMIT
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from chat.services.chat_history_manager.chat_message_saver import ChatMessageSaverService
from chat.services.kafka_workflow_response_handler import KafkaWorkflowResponseHandler, WahaMessageState
from chat.services.kafka_workflow_response_handler import WhatsAppMessageState
from chat.workflow_context import WorkflowContext
from chat.workflow_utils import extract_tool_info, push_waha_message_to_queue, remove_final_answer, push_llminfo_to_openmeter
from company.models import Company
from langchain_core.messages import  AIMessageChunk
from company.utils import CompanyUtils
from metering.services.openmeter import OpenMeter
from langfuse.decorators import observe, langfuse_context
from asgiref.sync import sync_to_async, async_to_sync
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)


class WorkflowRunner:
    def __init__(self):
        pass


    @observe()            
    async def run_workflow(
        self,
        workflow_name, 
        workflow_json, 
        workflow_type,
        workflow_stream,
        initial_message: str, 
        mobile_number: str, 
        session_id: str,
        client_session_id: str,
        client_identifier: str, 
        company: Company,
        openmeter_obj: OpenMeter,
        message_data: dict= {},
        message_payload={},
        save_ai_message=True,
        message_provider=None
        ):
    
        print(f"\ncompany in run_workflow: ",company,"\n")
        workflow_logger.add(f"company in run_workflow: {company}")
        
        # saving initial message in history
        extra_save_data = {
            'session_id': session_id if session_id else None,
            'client_session_id': client_session_id if client_session_id else None,
            'client_identifier': client_identifier if client_identifier else None,
            'message_id': message_data.get('message_id') if message_data else None,
            'message_type': message_data.get('message_type') if message_data else None,
            'billing_session_id' : openmeter_obj.billing_session_id,
            'request_id' : openmeter_obj.request_id,
            'request_medium' : openmeter_obj.api_controller.request_medium
        }
        extra_save_data = {k: v for k, v in extra_save_data.items() if v is not None}

        if message_data and 'media_url' in message_data.get('message_metadata', {}):
            if message_data['message_metadata']['media_url']:
                initial_message = initial_message+'\nFILE UPLOADED!' if initial_message else 'FILE UPLOADED!'

        chat_manager = InMemoryChatHistoryService(company=company, api_controller=openmeter_obj.api_controller, start_message=initial_message)
        chat_saver = ChatMessageSaverService(company=company, api_controller=openmeter_obj.api_controller, chat_manager=chat_manager)
        CompanyUtils.set_company_registry(company=company)

        if message_data and message_data.get('message_metadata'):
            _message_metadata = message_data.get('message_metadata')
        else:
            _message_metadata = message_payload.get('message', {}).get("metadata", {})
            
        if message_payload and message_payload.get('session_validated'):
            session_validated = True
        else:
            session_validated = False
        
        if initial_message:    
            await chat_saver.save_message(
                company=company,
                role='user',
                mobile_number=mobile_number,
                message=initial_message,
                extra_save_data=extra_save_data,
                client_identifier=client_identifier,
                message_metadata=_message_metadata,
                session_validated=session_validated,
                api_controller=openmeter_obj.api_controller
            )
            
            chat_history = [{'role': 'user', 'content':initial_message, 'message_metadata':_message_metadata}]

        else:
            chat_history = []

        send_tool_args = openmeter_obj.api_controller.is_tools_in_chat_history_enabled
        chat_history_processed = utils.strucutre_conversation_langchain(chat_history, send_tool_args = send_tool_args, reverse=False, openmeter_obj=openmeter_obj)
        
        # print("\n\n\nchat history sent to the chatbot",chat_history_processed,"\n\n")
        # workflow_logger.add(f"chat history sent to the chatbot{chat_history_processed}")

        workflow_factory_obj = WorkflowFactory()

        app = workflow_factory_obj.get_workflow(workflow_name, workflow_json, workflow_type=workflow_type)
        
        workflow_context = WorkflowContext(
            mobile=mobile_number,
            session_id=session_id,
            company=company,
            openmeter=openmeter_obj,
            message_payload=message_data,
            extra_save_data={
                "session_id": session_id,
                "client_identifier": client_identifier,
                'billing_session_id' : openmeter_obj.billing_session_id,
                'request_id' : openmeter_obj.request_id,
                'request_medium' : openmeter_obj.api_controller.request_medium,
                'message_metadata':message_data.get('metadata', {}) if message_data else None,
                'client_session_id': client_session_id if client_session_id else ''
            }
        )
        if not workflow_stream:
            response = self.get_response(app, chat_history_processed, company, mobile_number, extra_save_data, openmeter_obj, session_id, workflow_context, message_provider)
            async for res in response:
                yield res
            
        else:
            async for chunk in self.stream_response(app, chat_history_processed, company, mobile_number, extra_save_data, openmeter_obj, workflow_context, save_ai_message):
                yield chunk 
        
    @observe()
    async def stream_response(self, app, chat_history, company, mobile_number, extra_save_data, openmeter_obj, workflow_context, save_ai_message):
        final_output_nodes = []
        langfuse_handler = langfuse_context.get_current_langchain_handler()
        config = {
            "callbacks": [langfuse_handler],
            "configurable": {"thread_id": workflow_context.session_id}
        }
        
        serialized_workflow_context = workflow_context.to_dict()
        async for event in app.astream_events({"messages": chat_history, "workflow_context":serialized_workflow_context}, version="v1", config=config):
            if event['event'] == 'on_chain_end' and event['tags'] and 'graph' in event['tags'][0]:
                if event['name'] != '__start__':
                    final_output_nodes.append(event['data']['output'])
            if 'chunk' in event['data'] and isinstance(event['data']['chunk'], AIMessageChunk) and event['metadata']['include'] != 'no':

                yield event['data']['chunk'].content

        chat_saver = ChatMessageSaverService(company=company, api_controller=openmeter_obj.api_controller)
        for node_data in final_output_nodes:
            if node_data.get("include", "yes") == "no":
                continue

            messages = node_data.get('messages', [])

            if save_ai_message:
                for message in messages:
                    if isinstance(message, AIMessage):
                        if message.content:
                            if extra_save_data.get('message_metadata', None) and 'media_url' in extra_save_data['message_metadata']:
                                    extra_save_data['message_metadata']['media_url'] = ''

                            await chat_saver.save_message(
                                company=company,
                                role='assistant',
                                mobile_number=mobile_number,
                                message=message.content,
                                extra_save_data=extra_save_data,
                                client_identifier=workflow_context.extra_save_data['client_identifier'],
                                api_controller=openmeter_obj.api_controller
                            )
                        elif message.additional_kwargs.get('tool_calls'):
                            tool_calls = message.additional_kwargs.get('tool_calls')
                            tool_info = extract_tool_info(tool_calls)
                            for name, args in tool_info:
                                extra_save_data['function_name'] = name
                                if extra_save_data.get('message_metadata', None) and 'media_url' in extra_save_data['message_metadata']:
                                        extra_save_data['message_metadata']['media_url'] = ''

                                await chat_saver.save_message(
                                    company=company,
                                    role='function',
                                    mobile_number=mobile_number,
                                    message=json.dumps(args),
                                    extra_save_data=extra_save_data,
                                    client_identifier=workflow_context.extra_save_data['client_identifier']
                                )
                                extra_save_data['function_name'] = ""
                            
            push_llminfo_to_openmeter(node_data, openmeter_obj)
            
    @observe()
    async def get_response(self, app, chat_history_processed, company, mobile_number, extra_save_data, openmeter_obj, session_id, workflow_context, message_provider):
        
        langfuse_handler = langfuse_context.get_current_langchain_handler()
        config = {
            "callbacks": [langfuse_handler],
            "configurable": {"thread_id": session_id},
            "recursion_limit": 25
        }
        serialized_workflow_context = workflow_context.to_dict()
        
        events = app.astream({"messages": chat_history_processed, "workflow_context": serialized_workflow_context}, config=config)
        
        ai_output = []
        chat_saver = ChatMessageSaverService(company=company, api_controller=openmeter_obj.api_controller)

        waha_start_typing_message_sent = False
        
        async for event in events:
            if '__workflow_start__' in event: continue
            
            print("\n",event,"\n")
            workflow_logger.add(event)
            for node, node_data in event.items():
                
                messages = node_data.get('messages', [])
                for message in messages:
                    
                    if isinstance(message, AIMessage):
                        if message.content:
                            cleaned_content = remove_final_answer(message.content)
                            if node_data.get("include", "yes") != "no":
                                ai_output.append(cleaned_content)
                                
                            cleaned_content_ = cleaned_content
                            next_agent = ''
                            if node_data.get("response_format_schema") and "agent_redirect_response_format" in node_data.get("response_format_schema", ""):
                                try:
                                    json_response = json.loads(cleaned_content)
                                    cleaned_content_ = json_response.get("content", "")
                                    next_agent = json_response.get("next_agent", "")
                                except Exception as e:
                                    workflow_logger.add(f"Error in parsing agent_redirect_response_format: {e}")
                            
                            if not cleaned_content_ and not next_agent: continue
                            
                            if node_data.get("include", "yes") != "no":
                                yield cleaned_content_

                            extra_save_data['message_type'] = "text"
                            if extra_save_data.get('message_metadata', None) and 'media_url' in extra_save_data['message_metadata']:
                                    extra_save_data['message_metadata']['media_url'] = ''
                            
                            
                            if message_provider and message_provider.get("source") == "waha" and node_data.get("include", "yes") != "no" and cleaned_content_:
                                waha_start_typing_message_sent = True
                                await push_waha_message_to_queue(company, session_id, mobile_number, cleaned_content_, message_provider.get('waha_session'))
                                
                            
                            elif message_provider and node_data.get("include", "yes") != "no" and cleaned_content_:
                                wa_message = WhatsAppMessageState(
                                    phones=mobile_number,
                                    message=cleaned_content_,
                                    whatsapp_provider=message_provider.get("service_provider_company"),
                                    company_phone_number = message_provider.get("company_phone_number"),
                                    company=company,
                                    request_id=openmeter_obj.request_id
                                )
                                # print("wa_message", wa_message.get_wa_json_message())
                                KafkaWorkflowResponseHandler().push_wa_message_to_queue(wa_message=wa_message)

                                # provider_response = whatsapp_provider.send_chat_bot_reply(wa_message)
                                # extra_save_data['message_id'] = provider_response

                            conv_id = await chat_saver.save_message(
                                company=company,
                                role='assistant',
                                mobile_number=mobile_number,
                                message=cleaned_content_,
                                extra_save_data=extra_save_data,
                                client_identifier=workflow_context.extra_save_data['client_identifier'],
                                return_instance=True,
                                api_controller=openmeter_obj.api_controller
                            )

                            extra_save_data['message_id'] = conv_id

                        elif message.additional_kwargs.get('tool_calls'):
                            tool_calls = message.additional_kwargs.get('tool_calls')
                            tool_info = extract_tool_info(tool_calls)
                            for name, args in tool_info:

                                extra_save_data['message_type'] = "text"
                                extra_save_data['function_name'] = name
                                if extra_save_data.get('message_metadata', None) and 'media_url' in extra_save_data['message_metadata']:
                                    extra_save_data['message_metadata']['media_url'] = ''

                                await chat_saver.save_message(
                                    company=company,
                                    role='function',
                                    mobile_number=mobile_number,
                                    message=json.dumps(args),
                                    extra_save_data=extra_save_data,
                                    client_identifier=workflow_context.extra_save_data['client_identifier'],
                                    api_controller=openmeter_obj.api_controller
                                )
                                
                push_llminfo_to_openmeter(node_data, openmeter_obj)
        print("\n\nprinting response\n")
        print(ai_output)
        workflow_logger.add("printing stream")
        
        response = ''
        if len(ai_output) == 0:
            response = "Hey, how are you doing? How can I help you today?"
        else:
            for message in ai_output:
                response += message+"\n"
    
        print(response)
        workflow_logger.add(response)
        # return response
    