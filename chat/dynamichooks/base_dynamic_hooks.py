from backend.services.kafka_service import BaseKafkaService


class BaseDynamicHooks:
    
    QUEUE_NAME = "dynamic_hook_queue"
    
    def publish(self, dynamic_hook):
        BaseKafkaService().push(topic_name=self.QUEUE_NAME, message=dynamic_hook)
    
    def consume(self):
        pass