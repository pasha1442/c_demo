from backend.services.kafka_service import BaseKafkaService
from backend.settings.base import ENABLE_LANGFUSE_TRACING
from chat.dynamichooks.dynamic_hook import DynamicHook
from chat.services.conversation_manager_service import ConversationManagerService
from company.utils import CompanyUtils
from api_controller.models import ApiController
from langfuse.decorators import langfuse_context
import asyncio
import json
from basics.utils import Registry
from backend.constants import CURRENT_API_COMPANY
from concurrent.futures import ThreadPoolExecutor
from chat.constants import WRMQ_EXECUTOR_CONCURRENCY
from asgiref.sync import sync_to_async


class KafkaDynamicHookConsumer(BaseKafkaService):


    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.failure_queue_name = BaseKafkaService().get_failure_queue_name(queue_name)
        self.base_kafka_service = BaseKafkaService()

    async def consume_queue(self, queue_name):
        self.queue_name = queue_name if queue_name else self.queue_name
        consumer = self.base_kafka_service.pull(self.queue_name)
        
        for message in consumer:
            _payload = json.loads(message.value)
            client_identifier = _payload.get("client_identifier", "")
            if client_identifier:
                future = await self.handle_message(message)
            else:
                _error = f"Kafka Dynamic Hook Consumer Error: Invalid Client Identifier: {client_identifier}"
                print(_error)
                _payload["error"] = _error
                self.base_kafka_service.push(self.failure_queue_name, _payload)

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

        except Exception as e:
            print("Kafka Dynamic Hook Consumer Error:", str(e))
            _payload["error"] = str(e)
            self.base_kafka_service.push(self.failure_queue_name, _payload)

    async def process_message(self, company_id, _payload):
        company = await CompanyUtils.async_get_company_from_company_id(company_id)
        Registry().set(CURRENT_API_COMPANY, company)
        if company:
            langfuse_context.configure(
                secret_key=company.langfuse_secret_key,
                public_key=company.langfuse_public_key,
                enabled=ENABLE_LANGFUSE_TRACING
            )
            
            await DynamicHook(state=_payload, company=company).process()
