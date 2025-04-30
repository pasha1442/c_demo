from backend.services.kafka_service import BaseKafkaService
import logging
import json

logger = logging.getLogger(__name__)


class BaseDynamicHooks:
    
    QUEUE_NAME = "dynamic_hook_queue"
    
    def publish(self, dynamic_hook):
        BaseKafkaService().push(topic_name=self.QUEUE_NAME, message=dynamic_hook)
        
    def consume(self):
        pass
    
    async def process(self, company, state):
        
        try:
            logger.info(f"Processing {state.get('hook_type')} hook for company {company.name}")
            await self.execute(company, state)
            logger.info(f"Successfully executed {state.get('hook_type')} hook")
        except Exception as e:
            logger.error(f"Error executing {state.get('hook_type')} hook: {str(e)}")
            raise
    
    async def execute(self, company, state):
        raise NotImplementedError("Hook classes must implement execute method")