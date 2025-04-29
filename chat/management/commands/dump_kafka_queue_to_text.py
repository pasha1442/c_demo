from django.core.management.base import BaseCommand
import asyncio
import sentry_sdk
from sentry_sdk import start_transaction
from backend.settings.base import SENTRY_DSN_URL
from backend.services.kafka_service import BaseKafkaService

# Initialize Sentry
sentry_sdk.init(
    dsn=SENTRY_DSN_URL,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)


# python manage.py dump_kafka_queue_to_text failure_whatsapp_request_message_queue

class Command(BaseCommand):
    help = "Dump Queue into text"

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

                # Run the consumer within the asyncio event loop
                asyncio.run(self.run_consumer(queue_name))
                self.stdout.write(self.style.SUCCESS("Consumer executed successfully"))
            except Exception as ex:
                # Capture exceptions in Sentry
                sentry_sdk.capture_exception(ex)
                self.stdout.write(self.style.ERROR(f"Error: {ex}"))

    async def run_consumer(self, queue_name):
        # Add a span for the async operation
        with sentry_sdk.start_span(op="dump_kafka_queue_task", description="Running Kafka consumer"):
            print(f"Dump Started with: {queue_name}")
            consumer = BaseKafkaService().pull(queue_name)
            file_path = f"kafka_dump/{queue_name}.txt"
            with open(file_path, "a") as file:
                for message in consumer:
                    _message = message.value
                    print(f"Received message: {_message}")
                    try:
                        content = f"- {_message}\n"
                        file.write(content)
                    except Exception as e:
                        print("Error:", str(e))
