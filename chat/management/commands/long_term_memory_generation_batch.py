from backend.constants import KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE
from basics.commands import BaseCommand
from sentry_sdk import start_transaction
from backend.settings.base import SENTRY_DSN_URL
from datetime import datetime, timedelta
import asyncio
import sentry_sdk
import msgpack
from chat.models import ConversationSession
from django.utils import timezone
from asgiref.sync import sync_to_async
from backend.services.kafka_service import BaseKafkaService
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from chat.states.long_term_memory_queue_state import LongTermMemoryQueueState
from chat.utils import fetch_conversation_by_session_id
# Initialize Sentry
sentry_sdk.init(
    dsn=SENTRY_DSN_URL,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)



# python manage.py long_term_memory_generation_batch --hours 2
class Command(BaseCommand):
    help = "Long Term Memory Generation Batch"

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=2, help='Time window in hours for picking database entries (default: 2)')
        parser.add_argument('--buffer-mins', type=int, default=30, help='Buffer time in minutes to avoid processing recent sessions (default: 30)')
        parser.add_argument('--topic', type=str, default=KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE, 
                            help='Kafka topic name')

    def handle(self, *args, **options):
        # Get the logger
        self.init_logger('long_term_memory_generation_info')
        hours = options.get('hours', 2)
        buffer_mins = options.get('buffer_mins', 30)
        queue_name = options.get('topic', KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE)
        
        print(f"[DEBUG] handle() started with params: hours={hours}, buffer_mins={buffer_mins}, queue_name={queue_name}")
        
        # Start a Sentry transaction for tracing
        with start_transaction(op="batch_producer", name="Long Term Memory Generation Batch"):
            try:
                asyncio.run(self.run_producer(queue_name, hours, buffer_mins))
                print(f"Long Term Memory Generation Batch Started at: {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}, with queue name: {queue_name}, time window: {hours} hours")
                self.stdout.write(self.style.SUCCESS("Consumer executed successfully"))
            except Exception as ex:
                sentry_sdk.capture_exception(ex)
                self.stdout.write(self.style.ERROR(f"Error: {ex}"))

    async def run_producer(self, queue_name, hours, buffer_mins):
        print(f"[DEBUG] run_producer() started with queue_name={queue_name}, hours={hours}, buffer_mins={buffer_mins}")
        with sentry_sdk.start_span(op="producer_task", description="Running long term memory generation batch producer"):
            # Calculate the time threshold based on provided hours
            now = timezone.now()
            print(f"[DEBUG] Current time (timezone-aware): {now}")
            
            start_time_threshold = now - timedelta(hours=hours)
            end_time_threshold = now - timedelta(minutes=buffer_mins)
            
            session_records = await self.get_conversation_sessions(start_time_threshold, end_time_threshold)
            self.stdout.write(self.style.ERROR(f"Found {len(session_records)} conversation sessions to process"))

            print(f"[DEBUG] Starting asyncio.gather to process {len(session_records)} sessions")
            result = await asyncio.gather(
                *[self.process_session(session) for session in session_records]
            )
            print(f"[DEBUG] asyncio.gather completed with {len(result)} results")

    async def get_conversation_sessions(self, start_time_threshold, end_time_threshold):        
        @sync_to_async
        def fetch_sessions():
            query = ConversationSession.without_company_objects.filter(
                is_episodic_memory_created=False,
                created_at__gte=start_time_threshold,
                created_at__lte=end_time_threshold
            ).select_related('api_controller')
            result = list(query)
            return result
            
        result = await fetch_sessions()
        return result

    async def process_session(self, session):
        """Process a single conversation session"""
        print(f"[DEBUG] process_session() started for session_id={session.session_id}")
        try:
            @sync_to_async
            def get_session_attrs():
                return {
                    'company': session.company,
                    'client_identifier': session.client_identifier,
                    'session_id': session.session_id,
                    'api_controller': session.api_controller
                }
            
            attrs = await get_session_attrs()

            company = attrs['company']
            client_identifier = attrs['client_identifier']
            session_id = attrs['session_id']
            api_controller = attrs['api_controller']

            if not api_controller:
                self.stdout.write(self.style.WARNING(f"No api_controller for session {session_id}, skipping long term memory generation for {session_id}"))
                return
                        
            # Try to get chat history from cache first
            @sync_to_async
            def get_chat_history():
                try:
                    chat_history_cache_service = InMemoryChatHistoryService(company=company, api_controller=api_controller)
                    chat_history = chat_history_cache_service.get_chat_history_from_cache(company, client_identifier)
                    return chat_history
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error getting chat history from cache: {e}"))
                    return None
            
            chat_history = await get_chat_history()
            
            # If not in cache, fetch from database
            if not chat_history:
                print(f"[DEBUG] Fetching chat history from database for session_id={session_id}")
                
                @sync_to_async
                def fetch_history_from_db(session_id, company):
                    return fetch_conversation_by_session_id(session_id, company=company)
                    
                chat_history = await fetch_history_from_db(session_id, company)
            
            if not chat_history:
                self.stdout.write(self.style.WARNING(f"No chat history found for session {session_id}, skipping"))
                return
                        
            ltm_queue_data = LongTermMemoryQueueState(
                company_id=company.id,
                session_id=session_id,
                chat_history=chat_history,
                client_identifier=client_identifier,
                vector_storage_provider=api_controller.vector_storage_for_long_term_memory,
                workflow_id=api_controller.id,
                workflow_name=api_controller.name
            ).to_dict()
            
            # Push to queue
            @sync_to_async
            def push_to_queue(queue_data):
                try:
                    BaseKafkaService().push(KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE, queue_data)
                    return True
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error pushing to Kafka: {e}"))
                    raise
            
            await push_to_queue(ltm_queue_data)
            
            self.stdout.write(self.style.SUCCESS(f"Successfully pushed data to queue for session_id={session_id}"))
            
        except Exception as e:
            print(f"[DEBUG] Exception in process_session(): {e}")
            print(f"[DEBUG] Exception type: {type(e)}")
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            sentry_sdk.capture_exception(e)