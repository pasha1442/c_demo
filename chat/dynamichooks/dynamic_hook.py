import importlib
import logging
from datetime import datetime
from backend.services.kafka_service import BaseKafkaService
from company.models import CompanySetting


logger = logging.getLogger(__name__)

class DynamicHook:
    QUEUE_NAME = "dynamic_hook_queue"
    
    HOOK_PROCESSORS = {
        'summary_generation': 'chat.dynamichooks.hooks.summary_generator_dynamic_hook:SummaryGeneratorDynamicHook',
        'snooping_incoming_msg': 'chat.dynamichooks.hooks.snooping_incoming_msg_hook:SnoopingIncomingMsgHook',
        'snooping_outgoing_msg': 'chat.dynamichooks.hooks.snooping_outgoing_msg_hook:SnoopingOutgoingMsgHook'
    }
    
    def __init__(self, state, company=None):
        self.state = state
        self.company = company
        self.hook_type = state.get('hook_type')
        
        if self.hook_type not in self.HOOK_PROCESSORS:
            raise ValueError(f"Unknown hook type: {self.hook_type}")
        
        self.processor = self._lazy_import(self.HOOK_PROCESSORS[self.hook_type])

    @staticmethod
    def _lazy_import(import_path):
        module_name, class_name = import_path.split(':')
        try:
            module = importlib.import_module(module_name)
            return getattr(module, class_name)()
        except ImportError as e:
            logger.error(f"Failed to import {import_path}: {e}")
            raise

    @staticmethod
    def trigger_dynamic_hook(hook_type, company, **params):
        """
        Static method to trigger a dynamic hook by publishing to Kafka
        """
        try:
            if hook_type in ["snooping_incoming_msg", "snooping_outgoing_msg"]:
                params.setdefault('direction',
                    'incoming' if hook_type == 'snooping_incoming_msg' else 'outgoing'
                )

            hook_payload = {
                "hook_type": hook_type,
                "company_id": company.id,
                "timestamp": datetime.now().isoformat(),
                **params
            }

            queue_name = "dynamic_hook_queue"  
            
            setting = CompanySetting.objects.filter(
                company=company,
                key=CompanySetting.KEY_CHOICE_SNOOPING_WEBHOOK_URLS
            ).first()

            if setting and setting.queue_name:
                queue_name = setting.queue_name

            BaseKafkaService().push(topic_name=queue_name, message=hook_payload)
            logger.info(f"Triggered {hook_type} hook for company {company.name} on queue: {queue_name}")

        except Exception as e:
            logger.error(f"Error triggering {hook_type} hook: {str(e)}")
