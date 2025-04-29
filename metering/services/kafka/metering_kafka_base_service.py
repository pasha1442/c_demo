from backend.services.kafka_service import BaseKafkaService
from backend.constants import KAFKA_GLOBAL_OPENMETER_QUEUE


class MeteringKafkaService(BaseKafkaService):

    def __init__(self):
        super(MeteringKafkaService, self).__init__()
        self.queue_name = KAFKA_GLOBAL_OPENMETER_QUEUE
