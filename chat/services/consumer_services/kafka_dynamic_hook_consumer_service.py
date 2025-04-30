from backend.services.kafka_service import BaseKafkaService
from backend.settings.base import ENABLE_LANGFUSE_TRACING
from chat.dynamichooks.dynamic_hook import DynamicHook
from company.utils import CompanyUtils
from langfuse.decorators import langfuse_context
import asyncio
import json
from basics.utils import Registry
from backend.constants import CURRENT_API_COMPANY
import logging
from chat.dynamichooks.global_state_manager import GlobalCompanyStateManager


logger = logging.getLogger(__name__)

class KafkaDynamicHookConsumer(BaseKafkaService):
    """
    Consumer service for dynamic hooks from Kafka queue
    """

    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.failure_queue_name = BaseKafkaService().get_failure_queue_name(queue_name)
        self.base_kafka_service = BaseKafkaService()
        self.state_manager = GlobalCompanyStateManager()
        logger.info(f"Initialized KafkaDynamicHookConsumer with queue: {queue_name}")

    async def consume_queue(self, queue_name=None):
        """
        Consume messages from the specified Kafka queue
        
        Args:
            queue_name: Optional override for the queue name to consume
        """
        self.queue_name = queue_name if queue_name else self.queue_name
        logger.info(f"Starting consumer for queue: {self.queue_name}")
        
        consumer = self.base_kafka_service.pull(self.queue_name)
        
        for message in consumer:
            _payload = json.loads(message.value)
            client_identifier = _payload.get("client_identifier", "")
            logger.debug(f"Received message for client: {client_identifier}")
            
            if client_identifier:
                try:
                    await self.handle_message(message)
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    self._send_to_failure_queue(_payload, str(e))
            else:
                _error = f"Kafka Dynamic Hook Consumer Error: Invalid Client Identifier: {client_identifier}"
                logger.error(_error)
                self._send_to_failure_queue(_payload, _error)

    def _send_to_failure_queue(self, payload, error):
        """Helper to send messages to failure queue"""
        payload["error"] = error
        self.base_kafka_service.push(self.failure_queue_name, payload)

    async def handle_message(self, message):
        """
        Handles individual message processing with error handling and failure queue logic.
        """
        _payload = {}
        try:
            _payload = json.loads(message.value)
            company_id = _payload.get("company_id")
            if company_id:
                await self.process_message(company_id, _payload)
            else:
                raise ValueError("Missing company_id in payload")
        except Exception as e:
            logger.error(f"Kafka Dynamic Hook Consumer Error: {str(e)}")
            self._send_to_failure_queue(_payload, str(e))

    async def process_message(self, company_id, _payload):
        company = await CompanyUtils.async_get_company_from_company_id(company_id)
        Registry().set(CURRENT_API_COMPANY, company)
        
        if company:
            langfuse_context.configure(
                secret_key=company.langfuse_secret_key,
                public_key=company.langfuse_public_key,
                enabled=ENABLE_LANGFUSE_TRACING
            )
            
            hook_type = _payload.get('hook_type')
            logger.info(f"Processing {hook_type} hook for company {company.name}")
            
            try:
                await DynamicHook(state=_payload, company=company).process()
                logger.info(f"Successfully processed {hook_type} hook")
            except Exception as e:
                logger.error(f"Error processing {hook_type} hook: {str(e)}")
                raise
        else:
            raise ValueError(f"Company not found for ID: {company_id}")