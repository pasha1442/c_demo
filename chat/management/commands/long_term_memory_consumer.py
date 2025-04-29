from backend.constants import KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE
from basics.commands import BaseCommand
from sentry_sdk import start_transaction
from backend.settings.base import SENTRY_DSN_URL
from datetime import datetime
import asyncio
import sentry_sdk



# Initialize Sentry
sentry_sdk.init(
    dsn=SENTRY_DSN_URL,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)


# python manage.py long_term_memory_consumer long_term_memory_generation_queue

class Command(BaseCommand):
    help = "Long Term Memory Generation Consumer"

    def add_arguments(self, parser):
        parser.add_argument('topic', type=str)

    def handle(self, *args, **options):
        # Get the logger
        self.init_logger('long_term_memory_generation_info')
        # Start a Sentry transaction for tracing
        with start_transaction(op="kafka_consumer", name="Long Term Memort Generation Consumer"):
            try:
                queue_name = options.get('topic', KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE)
                if not queue_name:
                    self.stdout.write(self.style.ERROR('Invalid Queue Name'))
                    return

                # Run the consumer within the asyncio event loop
                print(f"Long Term Memory Generation Consumer Started at: {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}, with queue name : {queue_name}")
                asyncio.run(self.run_consumer(queue_name))

                self.stdout.write(self.style.SUCCESS("Consumer executed successfully"))
            except Exception as ex:
                # Capture exceptions in Sentry
                sentry_sdk.capture_exception(ex)
                self.stdout.write(self.style.ERROR(f"Error: {ex}"))

    async def run_consumer(self, queue_name):
        # Add a span for the async operation
        with sentry_sdk.start_span(op="consumer_task", description="Running Kafka consumer"):
            # Long Tem Memory Workflow Consumer
            from chat.services.consumer_services.ltm_generation_consumer_service import LTMGenerationConsumerService
            consumer = LTMGenerationConsumerService(queue_name=queue_name)
            await consumer.consume_queue(queue_name=queue_name)
