import asyncio
import sentry_sdk
from sentry_sdk import start_transaction
from backend.settings.base import SENTRY_DSN_URL
from basics.commands import BaseCommand
from chat.services.consumer_services.kafka_dynamic_hook_consumer_service import KafkaDynamicHookConsumer

# Initialize Sentry
sentry_sdk.init(
    dsn=SENTRY_DSN_URL,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# python manage.py kafka_dynamic_hook_consumer dynamic_hook_queue
class Command(BaseCommand):
    help = "Kafka Dynamic Hook Consumer"
    QUEUE_NAME = 'dynamic_hook_queue'
    
    def add_arguments(self, parser):
        parser.add_argument('queue', type=str, nargs='?', default=self.QUEUE_NAME,
                           help='Name of the Kafka queue to consume (default: dynamic_hook_queue)')

    def handle(self, *args, **options):
        # Start a Sentry transaction for tracing
        self.init_logger('dynamic_hook_info')
        
        with start_transaction(op="kafka_consumer", name="Kafka Dynamic Hook Consumer"):
            try:
                queue_name = options.get('queue')
                if not queue_name:
                    self.stdout.write(self.style.ERROR('Invalid Queue Name'))
                    return

                asyncio.run(self.run_consumer(queue_name))

                self.stdout.write(self.style.SUCCESS("Consumer executed successfully"))
            except Exception as ex:
                # Capture exceptions in Sentry
                sentry_sdk.capture_exception(ex)
                self.stdout.write(self.style.ERROR(f"Error: {ex}"))

    async def run_consumer(self, queue_name):
        with sentry_sdk.start_span(op="consumer_task", description="Running Kafka consumer"):
            consumer = KafkaDynamicHookConsumer(queue_name)
            await consumer.consume_queue(queue_name=queue_name)