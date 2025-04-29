from backend.services.kafka_service import BaseKafkaService


class BaseDynamicHooks:
    
    QUEUE_NAME = "dynamic_hook_queue"
    
    def publish(self, dynamic_hook):
        BaseKafkaService().push(topic_name=self.QUEUE_NAME, message=dynamic_hook)
        
    def consume(self):
        pass
    
    async def execute(self, company, state):
        """
        Base method that must be implemented by all hook classes
        
        Args:
            company: The company object
            state: The state data containing hook parameters
        """
        raise NotImplementedError("Hook classes must implement execute method")