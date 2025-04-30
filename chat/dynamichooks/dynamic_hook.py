from chat.dynamichooks.summary_generator_dynamic_hook import SummaryGeneratorDynamicHook
from chat.dynamichooks.hooks.snooping_incoming_msg_hook import SnoopingIncomingMsgHook
from chat.dynamichooks.hooks.snooping_outgoing_msg_hook import SnoopingOutgoingMsgHook
from chat.dynamichooks.hooks.nudging_hook import NudgingHook
from chat.dynamichooks.global_state_manager import GlobalCompanyStateManager
from backend.services.kafka_service import BaseKafkaService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Global state manager instance to be used across the module
state_manager = GlobalCompanyStateManager()

class DynamicHook:
    QUEUE_NAME = "dynamic_hook_queue"
    
    def __init__(self, state, company=None):
        
        self.hook_processors = {
            'summary_generation': SummaryGeneratorDynamicHook(),
            'snooping_incoming_msg': SnoopingIncomingMsgHook(),
            'snooping_outgoing_msg': SnoopingOutgoingMsgHook(),
            'nudging': NudgingHook()  
        }
        
        self.state = state
        self.company = company
        self.hook_type = state.get('hook_type')
        
        if self.hook_type in self.hook_processors:
            self.processor = self.hook_processors[self.hook_type]
        else:
            raise ValueError(f"Unknown hook type: {self.hook_type}")
    
    @staticmethod
    def trigger_dynamic_hook(hook_type, company, **params):
        """
        Static method to trigger a dynamic hook by publishing to Kafka
        
        Args:
            hook_type: Type of hook to trigger
            company: Company object
            params: Additional parameters for the hook
        """
        try:
            hook_payload = {
                "hook_type": hook_type,
                "company_id": company.id,
                "timestamp": datetime.now().isoformat(),
                **params
            }
            
            BaseKafkaService().push(topic_name="dynamic_hook_queue", message=hook_payload)
            logger.info(f"Triggered {hook_type} hook for company {company.name}")
            
        except Exception as e:
            logger.error(f"Error triggering {hook_type} hook: {str(e)}")
        
    async def process(self):
        try:
            company_id = str(self.company.id) if self.company else None
            if company_id:
                company_state = state_manager.get_company_state(company_id)
                
                if not company_state.get("webhook_urls") and self.company:
                    state_manager.fetch_and_cache_company_details(company_id)
            
            await self.processor.process(company=self.company, state=self.state)
            
            logger.info(f"Successfully processed {self.hook_type} hook for company {self.company.name if self.company else 'unknown'}")
            
        except Exception as e:
            logger.error(f"Error processing {self.hook_type} hook: {str(e)}")
            raise
        
    def publish(self):
        self.processor.publish(self.state)