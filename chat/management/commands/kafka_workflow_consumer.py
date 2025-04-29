from django.core.management.base import BaseCommand
import sentry_sdk
from sentry_sdk import start_transaction
from chat.services.consumer_services.kafka_workflow_consumer_service import KafkaWorkflowConsumer
from backend.settings.base import SENTRY_DSN_URL

# Initialize Sentry
sentry_sdk.init(
    dsn=SENTRY_DSN_URL,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)


# python manage.py kafka_workflow_consumer whatsapp_request_message_queue
# python manage.py kafka_workflow_consumer whatsapp_celery_request_message_queue

class Command(BaseCommand):
    help = "Kafka Workflow Consumer"

    def add_arguments(self, parser):
        parser.add_argument('topic', type=str)

    def handle(self, *args, **options):
        # Start a Sentry transaction for tracing
        with start_transaction(op="kafka_consumer", name="Kafka Workflow Consumer"):
            try:
                queue_name = options.get('topic')
                if not queue_name:
                    self.stdout.write(self.style.ERROR('Invalid Queue Name'))
                    return

                self.run_consumer(queue_name)

                self.stdout.write(self.style.SUCCESS("Consumer executed successfully"))
            except Exception as ex:
                # Capture exceptions in Sentry
                sentry_sdk.capture_exception(ex)
                self.stdout.write(self.style.ERROR(f"Error: {ex}"))

    def run_consumer(self, queue_name):
        with sentry_sdk.start_span(op="consumer_task", description="Running Kafka consumer"):
            consumer = KafkaWorkflowConsumer(queue_name)
            consumer.consume_queue(queue_name=queue_name)