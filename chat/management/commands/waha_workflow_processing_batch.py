import time

import pytz
from backend.constants import KAFKA_GLOBAL_WAHA_REQUEST_MESSAGE_QUEUE
from basics.commands import BaseCommand
from sentry_sdk import start_transaction
from backend.settings.base import SENTRY_DSN_URL
from datetime import datetime, timedelta
import asyncio
import sentry_sdk
import msgpack
from chat.models import ConversationSession, Conversations
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



# python manage.py waha_workflow_processing_batch --hours 2
class Command(BaseCommand):
    help = "WAHA workflow processing Batch"

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=2, help='Time window in hours for picking session database entries (default: 2)')
        parser.add_argument('--topic', type=str, default=KAFKA_GLOBAL_WAHA_REQUEST_MESSAGE_QUEUE, help='Kafka topic name')
        parser.add_argument('--user_message_elapsed_minutes', type=int, default=5, help='User message minimum elapsed minutes which needs to process')

    def handle(self, *args, **options):
        # Get the logger
        self.init_logger('waha_workflow_processing_batch_info')
        hours = options.get('hours', 2)
        queue_name = options.get('topic', KAFKA_GLOBAL_WAHA_REQUEST_MESSAGE_QUEUE)
        user_message_elapsed_minutes = options.get('user_message_elapsed_minutes', 5)
        
        print(f"[DEBUG] handle() started with params: hours={hours}, queue_name={queue_name}, user_message_elapsed_minutes={user_message_elapsed_minutes}")
        
        # Start a Sentry transaction for tracing
        with start_transaction(op="batch_producer", name="WAHA Workflow Processing Batch"):
            try:
                asyncio.run(self.run_producer(queue_name, hours, user_message_elapsed_minutes))
                print(f"WAHA Workflow Processing Batch Started at: {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}, with queue name: {queue_name}, time window: {hours} hours")
                self.stdout.write(self.style.SUCCESS("Consumer executed successfully"))
            except Exception as ex:
                sentry_sdk.capture_exception(ex)
                self.stdout.write(self.style.ERROR(f"Error: {ex}"))

    async def run_producer(self, queue_name, hours, user_message_elapsed_minutes):
        print(f"[DEBUG] run_producer() started with queue_name={queue_name}, hours={hours}, user_message_elapsed_minutes={user_message_elapsed_minutes}")
        with sentry_sdk.start_span(op="producer_task", description="Running waha workflow processing batch producer"):
            # Calculate the time threshold based on provided hours
            
            start_time_threshold = timezone.now() - timedelta(hours=hours)
            print(start_time_threshold)
            
            session_records = await self.get_conversation_sessions(start_time_threshold)
            self.stdout.write(self.style.ERROR(f"Found {len(session_records)} conversation sessions to process"))

            processable_session_records = await self.get_processable_sessions(session_records, user_message_elapsed_minutes)
            
            print(f"[DEBUG] Starting asyncio.gather to process {len(processable_session_records)} sessions")
            result = await asyncio.gather(
                *[self.process_session(session) for session in processable_session_records]
            )
            print(f"[DEBUG] asyncio.gather completed with {len(result)} results")

    async def get_conversation_sessions(self, start_time_threshold):
        @sync_to_async
        def fetch_sessions():
            query = ConversationSession.without_company_objects.filter(
                created_at__gte=start_time_threshold,
                request_medium='waha'
            ).select_related('api_controller')
            result = list(query)
            return result
            
        result = await fetch_sessions()
        return result

    async def get_processable_sessions(self, sessions, user_message_elapsed_minutes):
        @sync_to_async
        def fetch_history_from_db(session_id, company=None):
            return fetch_conversation_by_session_id(session_id, company)
        
        @sync_to_async
        def get_session_attrs():
            return {
                'company': session.company,
                'client_identifier': session.client_identifier,
                'session_id': session.session_id,
                'api_controller': session.api_controller
            }
            
        
        
        #Filter 1: for each (client_identifer, api_controller) pick latest session
        mapping = {}
        for session in sessions:
            client_identifier = session.client_identifier
            api_route = session.api_controller.api_route
            
            if client_identifier not in mapping:
                mapping[client_identifier] = {}
            
            if api_route not in mapping[client_identifier] or session.created_at > mapping[client_identifier][api_route].created_at:
                mapping[client_identifier][api_route] = session
        
        #Filter 2: Pick only those sessions for which ignore_session if False    
        processable_sessions = [session for client in mapping.values() for session in client.values() if not session.ignore_session]

        #Filter 3: Pick sessions where the user's message was sent more than X minutes ago.
        final_processable_sessions = []        
        for session in processable_sessions:
            attrs = await get_session_attrs()
            session_messages = await fetch_history_from_db(session.session_id, attrs['company'])
            
            last_valid_user_message_time = datetime.now(timezone.utc)
            
            for message in session_messages:
                print(message)
                if message['role'] in {'assistant', 'function'}: break
                last_valid_user_message_time = datetime.strptime(message['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ")
            
            print(last_valid_user_message_time)
            
            ist_time = last_valid_user_message_time.astimezone(pytz.timezone('Asia/Kolkata')).timestamp()
            
            if int(time.time()) - ist_time >= user_message_elapsed_minutes*60:
                final_processable_sessions.append(session)
              
        return final_processable_sessions
    
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
                    'api_controller': session.api_controller,
                    'waha_session': session.client_session_id,
                    'company_phone_number':session.api_controller.phone_number
                }
            
            attrs = await get_session_attrs()

            company = attrs['company']
            client_identifier = attrs['client_identifier']
            session_id = attrs['session_id']
            api_controller = attrs['api_controller']
            waha_session = attrs['waha_session']
            company_phone_number = attrs['company_phone_number']
            
            print(company_phone_number)
            
            print(api_controller)
            print(client_identifier)
            waha_data = {'source': 'waha',
                    'company_phone_number': company_phone_number, 'company_id': company.id,
                    'sender': client_identifier, 'message_id': 'wamid.HBgMOTE4NTYwMDQwOTU3FQIAEhgUM0FERDVEQTVCMTI3MDY4MzZCRkUA',
                    'message': "", 'message_type': 'text', 'media_url': None,
                    'timestamp': '', 'transaction_id': '01JE3DXWJ9GB9BHQ9PPC6XRT6Y', 'waha_session': waha_session, 'client_identifier': client_identifier}
            
            print(waha_data)
            BaseKafkaService().push(topic_name=KAFKA_GLOBAL_WAHA_REQUEST_MESSAGE_QUEUE, message=waha_data)
            
            self.stdout.write(self.style.SUCCESS(f"Successfully pushed data to queue for session_id={session_id}"))
            
        except Exception as e:
            print(f"[DEBUG] Exception in process_session(): {e}")
            print(f"[DEBUG] Exception type: {type(e)}")
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            sentry_sdk.capture_exception(e)