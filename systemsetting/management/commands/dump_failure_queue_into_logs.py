import datetime
import json
import time

from django.core.management import BaseCommand

from backend.logger import Logger
from backend.services.kafka_service import BaseKafkaService
from basics.utils import DateTimeConversion
from systemsetting.api.views import DataProcessingQueueManager
from systemsetting.models import DataProcessingQueue

failure_queue_logger = Logger(Logger.FAILURE_QUEUE_LOG)
class Command(BaseCommand):
    help = "Get Failure Queue and fetch his data and write logs."

    def handle(self, *args, **options):
        active_queues = DataProcessingQueue.objects.filter(is_active=True).values('id', 'name', 'queue_name')
        queue_list_data = list(active_queues)
        queue_list = []
        if queue_list_data:
            for q_list in queue_list_data:
                queue_name = q_list.get("queue_name")
                failure_queue_name = BaseKafkaService().get_failure_queue_name(topic_name=queue_name)
                queue_consume = BaseKafkaService().pull_message_with_timeout(topic_name=failure_queue_name, timeout_sec=30)

                try:
                    for data in queue_consume:
                        _payload = json.loads(data.value)
                        if _payload:
                            timestamp = _payload.get("timestamp")
                            timestamp = timestamp if timestamp is not None or timestamp != "" else DateTimeConversion.to_string(datetime.datetime.now())
                            failure_queue_logger.add(
                                f"Queue - {failure_queue_name} | Timestamp: {timestamp} | Message : {_payload}")
                    time.sleep(5)
                except Exception as e:
                    print(f"Error while consuming from queue {failure_queue_name}: {e}")
                finally:
                    # Close the consumer before moving to the next queue
                    queue_consume.close()
                    print(f"Consumer closed for queue: {failure_queue_name}")




