from metering.services.kafka.metering_kafka_base_service import MeteringKafkaService
from backend.services.kafka_service import BaseKafkaService
from metering.services.openmeter import OpenMeter
from company.utils import CompanyUtils
import json


class MeteringKafkaConsumer(MeteringKafkaService):

    def consume_events_from_queue(self):
        print("Consumer Started For:", self.queue_name)
        consumer = BaseKafkaService().pull(self.queue_name)

        for message in consumer:
            _payload = json.loads(message.value)
            print(f"Received message: {_payload}")
            _company_id = _payload.get("company_id", None)
            if _company_id:
                _company_obj = CompanyUtils.get_company_from_company_id(company_id=_company_id)
                OpenMeter(company=_company_obj).publish_event_to_openmeter(_payload)
            else:
                print(f"Error: Invalid Company ID: {_company_id}")
