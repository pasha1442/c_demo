import asyncio
import json
import time
import requests
from decouple import config

from backend.services.kafka_service import BaseKafkaService
from backend.testing import BaseUnitTestCase
from basics.utils import UUID
from chat.services.consumer_services.kafka_workflow_consumer_service import KafkaWorkflowConsumer


class BaseTestCases(BaseUnitTestCase):
    GEETA = "geeta"
    AURIGA = "auriga"
    KINDLIFE_BIZZ = "kindlife_bizz"
    KINDLIFE = "kindlife"
    OMF_CHAT = "omf_chat"
    RECOBEE = "recobee"
    STITCH = "stitch"
    TR_CAPITAL = "tr_capital"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class APIBasedTestCases(BaseTestCases):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.core_server_base_url = config("UNIT_TESTS_API_BASE_URL", "http://localhost:8080")

    def get_company_auth_token(self, company_name=None):
        auth_token = None
        if company_name:
            tokens = config("UNIT_TESTS_API_COMPANY_TOKENS")
            tokens = json.loads(tokens)

            auth_token = tokens.get(company_name)
        return auth_token

    def generate_bot_payload(self, message="Hi"):
        self.session_id = f"test-session-{UUID.get_uuid()}"

        payload = {"mobile": self.session_id, "client_identifier": self.session_id, "session_id": self.session_id,
                   "text": message}
        return payload

    def get_bot_header(self, company_name):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.get_company_auth_token(company_name)}'
        }

        return headers

    def post_api_request(self, base_url=None, payload=None, headers=None, wait_for_full_response=False,
                         wait_time_in_sec=5):
        if headers is None:
            headers = {}
        if payload is None:
            payload = {}
        status = True
        error_message = ""
        status_code = None
        text_message = None
        try:
            response = requests.post(base_url, json=payload, headers=headers)
            status_code = response.status_code

            if wait_for_full_response:
                time.sleep(wait_time_in_sec)
                text_message = response.text
        except Exception as e:
            status = False
            error_message = str(e)

        return {"status": status, "error_message": error_message, "status_code": status_code,
                "text_response": text_message}


class QueueBasedTestCases(BaseTestCases):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_sample_message_by_company(self, company_name=None):
        message = None
        if company_name:
            test_message = {
                "tr_capital":{'source': 'whatsapp', 'service_provider_company': 'Meta',
                'company_phone_number': '919079195331', 'company_id': 9,
                'sender': '916375051834',
                'message_id': 'wamid.HBgMOTE4NTYwMDQwOTU3FQIAEhgUM0FERDVEQTVCMTI3MDY4MzZCRkUA',
                'message': "Hii TR", 'message_type': 'text', 'media_url': None,
                'timestamp': '', 'transaction_id': '01JE3DXWJ9GB9BHQ9PPC6XRT6Y', 'client_identifier': '916375051834'}
            }
            message = test_message.get(company_name)
        return message

    def handle_message_for_test(self, topic_name = None, message=None):
        """
        Handles individual message processing with error handling and failure queue logic.
        """
        _payload = {}
        er_message = ""
        status = True
        KafkaWorkflowConsumerObject = KafkaWorkflowConsumer(queue_name=topic_name)
        try:
            print("Handle Message")
            _payload = json.loads(message.value)
            print(f"Received message: {_payload}")
            company_id = _payload.get("company_id")
            if company_id:
                asyncio.run(KafkaWorkflowConsumerObject.process_message(company_id, _payload))
                # await asyncio.get_event_loop().run_in_executor(self.executor, self.process_message1, company_id, _payload)
        except Exception as e:
            er_message = str(e)
            status = False

        return {"status": status, "message": er_message}

    def push_test_message(self, topic_name=None, message=None):
        status = True
        error_message = ""
        if topic_name and topic_name.strip() != "":
            try:
                kafka_object = BaseKafkaService(topic_name=topic_name)
                result = kafka_object.push(topic_name=topic_name, message=message)
            except Exception as e:
                status = False
                error_message = str(e)
        else:
            status = False
            error_message = "Topic name is missing."

        return {"status": status, "message": error_message}

    def pull_test_message(self, topic_name=None):
        status = False
        return_message = "message not found"
        if topic_name and topic_name.strip() != "":
            try:
                kafka_object = BaseKafkaService(topic_name=topic_name)
                consume = kafka_object.pull_message_with_timeout(topic_name=topic_name, timeout_sec=5)
                for data in consume:
                    _payload = json.loads(data.value)
                    if _payload:
                        status = True
                        return_message = data


                    consume.close()
            except Exception as e:
                return_message = str(e)
            finally:
                consume.close()
        else:
            status = False
            return_message = "Topic name is missing."

        return {"status": status, "message": return_message}
