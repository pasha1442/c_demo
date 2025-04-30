# chat/dynamichooks/hooks/nudging_hook.py

from chat.dynamichooks.base_dynamic_hooks import BaseDynamicHooks
import logging
import json
from asgiref.sync import sync_to_async
from api_controller.models import ApiController
from chat.services.kafka_workflow_response_handler import KafkaWorkflowResponseHandler, WhatsAppMessageState

logger = logging.getLogger(__name__)

class NudgingHook(BaseDynamicHooks):
    """
    Hook for sending nudge messages to inactive users
    """
    
    async def execute(self, company, state):
        """
        Execute the nudging functionality
        
        Args:
            company: The company object
            state: The state data containing hook parameters
        """
        logger.info(f"Processing nudge for {state.get('client_identifier')}")
        
        client_identifier = state.get('client_identifier')
        session_id = state.get('session_id')
        customer_mobile = state.get('customer_mobile')
        nudge_template = state.get('nudge_template', 'default_nudge')
        
        if not client_identifier or not session_id or not customer_mobile:
            logger.warning("Missing required parameters for nudging")
            return
            
        api_controller = None
        if state.get('api_route'):
            try:
                api_controller = await sync_to_async(ApiController.without_company_objects.get)(
                    api_route=state.get('api_route'), company=company
                )
            except Exception as e:
                logger.error(f"Error fetching API controller: {e}")
        
        nudge_message = self._get_nudge_message(company, nudge_template)
        
        try:
            wa_message = WhatsAppMessageState(
                phones=customer_mobile,
                message=nudge_message,
                company=company,
                whatsapp_provider=self._get_provider_from_company(company),
                company_phone_number=self._get_company_phone(company, api_controller),
            )
            
            KafkaWorkflowResponseHandler().push_wa_message_to_queue(wa_message=wa_message)
            
            logger.info(f"Successfully sent nudge message to {customer_mobile}")
            
            from chat.services.chat_history_manager.chat_message_saver import ChatMessageSaverService
            chat_saver = ChatMessageSaverService(company=company, api_controller=api_controller)
            
            extra_save_data = {
                'session_id': session_id,
                'client_identifier': client_identifier,
                'message_type': "text",
            }
            
            await chat_saver.save_message(
                company=company,
                role='assistant',
                mobile_number=customer_mobile,
                message=nudge_message,
                extra_save_data=extra_save_data,
                client_identifier=client_identifier,
                api_controller=api_controller
            )
            
        except Exception as e:
            logger.error(f"Error sending nudge message: {e}")
    
    def _get_nudge_message(self, company, template_name):
        """Get the appropriate nudge message template"""
        
        default_nudge = "Hey there! Just checking if you need any further assistance?"
        
        if hasattr(company, 'message_templates') and company.message_templates:
            templates = json.loads(company.message_templates) if isinstance(company.message_templates, str) else company.message_templates
            return templates.get(template_name, default_nudge)
            
        return default_nudge
    
    def _get_provider_from_company(self, company):
        """Extract the WhatsApp provider from company settings"""
        if hasattr(company, 'whatsapp_provider'):
            return company.whatsapp_provider
        return "Meta"  
    
    def _get_company_phone(self, company, api_controller):
        if api_controller and hasattr(api_controller, 'phone_number'):
            return api_controller.phone_number
        
        if hasattr(company, 'phone_number'):
            return company.phone_number
        
        return None  