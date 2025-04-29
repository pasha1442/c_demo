from backend.services.kafka_service import BaseKafkaService
from backend.settings.base import ENABLE_LANGFUSE_TRACING
from company.utils import CompanyUtils
from api_controller.models import ApiController
import chat.utils as utils
from metering.services.openmeter import OpenMeter
from langfuse.decorators import langfuse_context
import asyncio
import json
from asgiref.sync import sync_to_async, async_to_sync
from backend.services.celery_service import CeleryService
from backend.services.cache_service import CacheService
from chat.states.workflow_celery_cache_state import WorkflowCeleryCacheState
from datetime import datetime, timedelta
from basics.utils import DateTimeConversion as DTC
from backend.constants import KAFKA_GLOBAL_WHATSAPP_CELERY_REQUEST_MESSAGE_QUEUE
from concurrent.futures import ThreadPoolExecutor
from chat.constants import WRMQ_EXECUTOR_CONCURRENCY
import newrelic.agent

class CeleryWorkflowConsumer(BaseKafkaService):

    def __init__(self):
        self.celery_obj = CeleryService()
        self.cache = CacheService(cache_db=CacheService.CACHE_DB_CELERY_WORKFLOW_CACHE)

    @staticmethod
    def check_and_execute_workflow(_client_identifier):
        print("Workflow Checker Initiated for: ", _client_identifier)
        _celery_workflow = CeleryWorkflowConsumer()
        _cache_messages = _celery_workflow.cache.get(_client_identifier)
        _execution_time = _cache_messages.get("execution_time")
        if _execution_time and DTC.str_to_datetime(_execution_time) <= datetime.now():
            _combined_message = _celery_workflow.get_combined_message(_cache_messages)
            BaseKafkaService().push(KAFKA_GLOBAL_WHATSAPP_CELERY_REQUEST_MESSAGE_QUEUE, _combined_message)
            _cache_messages["messages"] = []
            _celery_workflow.cache.set(_client_identifier, _cache_messages)
            print(
                f"Delayed Celery Task Completed for {_client_identifier}, Messaged Pushed to '{KAFKA_GLOBAL_WHATSAPP_CELERY_REQUEST_MESSAGE_QUEUE}' queue")
        else:
            print("Task Delay Not Matched.")

    def get_combined_message(self, _cache_messages):
        _combined_msg, _cache_msgs = {}, _cache_messages.get("messages", [])
        _texts, _media_urls = [], []
        if _cache_msgs:
            _combined_msg = _cache_msgs[0]
            for _cache_msg in _cache_msgs:
                if _cache_msg.get('message_type') in ["text"]:
                    _texts.append(_cache_msg.get('message'))
                elif _cache_msg.get('message_type') in ["image", "document"]:
                    _media_urls.append(_cache_msg.get('media_url'))
                    _texts.append("File Uploaded")
            _combined_msg["message"] = ",".join(_texts)
            _combined_msg["media_url"] = ",".join(_media_urls)
        else:
            print("Empty Messages Cache.")
        return _combined_msg

    async def consume_queue(self, queue_name):
        print("Consumer Started For:", queue_name)
        consumer = BaseKafkaService().pull(queue_name)
        tasks = []  # Collect tasks here

        for message in consumer:
            try:
                _payload = json.loads(message.value)
                print(f"Received message: {_payload}")
                _client_identifier = _payload.get("sender")
                if _client_identifier:
                    task = self.save_message_in_cache(_client_identifier, _payload)
                    tasks.append(task)
                    await asyncio.gather(*[task])
            except Exception as e:
                print("Error: ", str(e))
                _message = _payload
                _message["error"] = str(e)
                _failure_queue_name = BaseKafkaService().get_failure_queue_name(queue_name)
                BaseKafkaService().push(_failure_queue_name, _message)

    async def save_message_in_cache(self, _client_identifier, _payload):
        _existing_cache = self.cache.get(_client_identifier)
        _new_cache = {}
        _delay_delta = self.get_delay_delta(_payload)
        _current_time = datetime.now()
        company_id = _payload.get("company_id", None)
        if not _existing_cache:
            _new_cache = WorkflowCeleryCacheState(company_id=company_id,
                                                  client_identifier=_client_identifier,
                                                  thread_start_at=DTC.to_string(_current_time),
                                                  execution_time=DTC.to_string(
                                                      _current_time + timedelta(seconds=_delay_delta)),
                                                  messages=[_payload]
                                                  ).to_dict()
            self.cache.set(_client_identifier, _new_cache)
        else:
            if not _existing_cache["messages"]:
                _existing_cache["thread_start_at"] = DTC.to_string(_current_time)

            _existing_cache["execution_time"] = DTC.to_string(
                _current_time + timedelta(seconds=_delay_delta))
            _existing_cache["messages"].append(_payload)
            self.cache.set(_client_identifier, _existing_cache)

        await self.init_celery_execution_checker(_client_identifier, _delay_delta)

    async def init_celery_execution_checker(self, _client_identifier, countdown=5):
        print(f"Scheduling Task for {_client_identifier} with {countdown} Seconds Delay ")
        self.celery_obj.schedule_task(
            task_name=f"workflow_checker_{_client_identifier}",
            countdown=countdown,  # Run after 5 seconds
            args=(_client_identifier,),
            kwargs={"func_name": "CeleryTools.workflow_execution_checker"}
        )

    def get_delay_delta(self, _payload):
        _message_type = _payload.get("message_type", None)
        if _message_type in ["image", "document"]:
            return 5
        elif _message_type in ["text"]:
            return 2
        return 5


class KafkaWorkflowConsumer(BaseKafkaService):

    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.failure_queue_name = BaseKafkaService().get_failure_queue_name(queue_name)
        self.base_kafka_service = BaseKafkaService()
        self.executors = {
            "0": ThreadPoolExecutor(max_workers=1),
            "1": ThreadPoolExecutor(max_workers=1),
            "2": ThreadPoolExecutor(max_workers=1),
            "3": ThreadPoolExecutor(max_workers=1),
            "4": ThreadPoolExecutor(max_workers=1),
            "5": ThreadPoolExecutor(max_workers=1),
            "6": ThreadPoolExecutor(max_workers=1),
            "7": ThreadPoolExecutor(max_workers=1),
            "8": ThreadPoolExecutor(max_workers=1),
            "9": ThreadPoolExecutor(max_workers=1)
        }

    def get_executor(self, client_identifier):
        executor_partition_key = f"{client_identifier}"
        hash_value = self.get_hash_encoded_value(executor_partition_key)
        _executor_value = self.executors.get(str(hash_value % WRMQ_EXECUTOR_CONCURRENCY))
        return _executor_value

    def consume_queue(self, queue_name):
        self.queue_name = queue_name if queue_name else self.queue_name
        consumer = self.base_kafka_service.pull(self.queue_name)
        for message in consumer:
            _payload = json.loads(message.value)
            client_identifier = _payload.get("client_identifier", "")
            if client_identifier:
                _executor = self.get_executor(client_identifier)
                try:
                    print("exe", _executor)
                    future = _executor.submit(self.handle_message, message)
                    # future.add_done_callback(lambda f: _executor.shutdown(wait=True))
                except Exception as e:
                    print("Exception", str(e))
            else:
                _error = f"Kafka Workflow Consumer Error: Invalid Client Identifier: {client_identifier}"
                print(_error)
                _payload["error"] = _error
                self.base_kafka_service.push(self.failure_queue_name, _payload)

    def handle_message(self, message):
        """
        Handles individual message processing with error handling and failure queue logic.
        """
        _payload = {}
        try:
            print("Handle Message")
            _payload = json.loads(message.value)
            print(f"Received message: {_payload}")
            company_id = _payload.get("company_id")
            if company_id:
                asyncio.run(self.process_message(company_id, _payload))
                # await asyncio.get_event_loop().run_in_executor(self.executor, self.process_message1, company_id, _payload)
        except Exception as e:
            print("Kafka Workflow Consumer Error:", str(e))
            _payload["error"] = str(e)
            self.base_kafka_service.push(self.failure_queue_name, _payload)

    async def process_message(self, company_id, _payload):
        company = await CompanyUtils.async_get_company_from_company_id(company_id)
        if company:
            langfuse_context.configure(
                secret_key=company.langfuse_secret_key,
                public_key=company.langfuse_public_key,
                enabled=ENABLE_LANGFUSE_TRACING
            )
            await self.init_workflow_consumer(company, _payload)
            # await self.init_workflow_consumer(company, _payload)

    async def init_workflow_consumer(self, company, _payload):
        print("wa_request", _payload)

        customer_mobile = _payload.get("sender")
        request_id = _payload.get("request_id", "")

        api_controller = await sync_to_async(ApiController.without_company_objects.get)(
            phone_number=_payload.get("company_phone_number")
        )
        required_data = {
            'source': _payload.get("source"),
            'text': _payload.get("message"),
            'customer_mobile': _payload.get("sender"),
            'message_type': _payload.get("message_type"),
            'message_id': _payload.get("message_id"),
            'media_url': _payload.get("media_url"),
            'company_phone_number': _payload.get("company_phone_number"),
            "service_provider_company": _payload.get("service_provider_company"),
            "request_id": request_id,
            'client_identifier': customer_mobile,
        }
        
        if _payload.get('source') == 'waha':
            required_data['waha_session'] = _payload.get('waha_session')
            
        om_obj = OpenMeter(company=company, api_controller=api_controller,
                           request_args={"session_id": customer_mobile,
                                         "request_id": request_id})

        try:
            company_name = company.name
            txn_name = f"{company_name}/{api_controller.api_route}/whatsapp"
            newrelic.agent.set_transaction_name(txn_name)
        except Exception as nr_error:
            print(f"New Relic naming error (non-critical): {nr_error}")

        response = await utils.handle_dynamic_webhook_message(
            company=company,
            api_controller=api_controller,
            data=required_data,
            openmeter_obj=om_obj,
            workflow_name=""
        )

        # Ingest Openmeter API Call API call
        await sync_to_async(om_obj.ingest_api_call)(
            api_method="webhook/v1/whatsapp/send-message/"
        )
