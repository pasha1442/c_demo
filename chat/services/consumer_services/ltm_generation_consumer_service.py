# Long term memory generation consumer service
import asyncio
from datetime import datetime
import json
from backend.services.kafka_service import BaseKafkaService
from backend.settings.base import ENABLE_LANGFUSE_TRACING
from langfuse.decorators import langfuse_context



class LTMGenerationConsumerService(BaseKafkaService):
    # Long term memory generation consumer

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
            print(f"Long Term Memory Generation Started for client_identifier : {client_identifier}: {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}")
            if client_identifier:
                future = await self.handle_message(message=message)
            else:
                _error = f"Kafka Workflow Consumer Error: Invalid Client Identifier: {client_identifier}"
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
                asyncio.run(self.process_message(company_id, _payload))
        except Exception as e:
            print("Kafka Long Term Memory Consumer Error:", str(e))
            _payload["error"] = str(e)
            self.base_kafka_service.push(self.failure_queue_name, _payload)

    async def process_message(self, company_id, _payload):
        from company.utils import CompanyUtils
        company = await CompanyUtils.async_get_company_from_company_id(company_id)

        if company:
            langfuse_context.configure(
                secret_key=company.langfuse_secret_key,
                public_key=company.langfuse_public_key,
                enabled=ENABLE_LANGFUSE_TRACING
            )
            await self.init_ltm_generation_consumer(company, _payload)

    async def init_ltm_generation_consumer(self, company, _payload):
        from chat.services.long_term_memory_generation_service import LongTermMemoryGenerationService
        ltm_generator = LongTermMemoryGenerationService(company=company)

        response = await ltm_generator.generate_long_term_memory(
            company=company,
            client_identifier=_payload.get("client_identifier"),
            session_id=_payload.get("session_id"),
            chat_history=_payload.get("chat_history"),
            vector_storage_provider=_payload.get("vector_storage_provider"),
            workflow_name=_payload.get("workflow_name"),
            workflow_id=_payload.get("workflow_id"),
        )