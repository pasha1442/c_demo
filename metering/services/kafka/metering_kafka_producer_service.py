from metering.services.kafka.metering_kafka_base_service import MeteringKafkaService


class MeteringKafkaProducer(MeteringKafkaService):

    async def push_openmeter_raw_data_in_kafka(self, data):
        self.push(self.queue_name, data)
