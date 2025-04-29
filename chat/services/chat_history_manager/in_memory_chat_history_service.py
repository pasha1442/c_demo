from datetime import datetime
from api_controller.models import ApiController
from backend.services.cache_service import CacheService
from basics.utils import EncodeDecodeUTF8
from chat.constants import CHAT_HISTORY_MESSAGES_WITH_SUMMARY_LIMIT, IN_MEMORY_CHAT_HISTORY_MESSAGE_LIMIT, IN_MEMORY_CHAT_HISTORY_TIME_LIMIT, SUMMARY_GENERATION_TRIGGER_LIMIT
from chat.services.chat_history_manager.persistent_chat_history_service import PersistentChatHistoryService
from chat.states.In_memory_message_state import InMemoryMessageState
from chat.states.llm_message_state import LLMMessageState
from chat.states.long_term_memory_queue_state import LongTermMemoryQueueState
from company.utils import CompanyUtils
from metering.services.session_service import SessionManager
import msgpack
from backend.logger import Logger

redis_logger = Logger(Logger.REDIS_LOG)



class InMemoryChatHistoryService:
    def __init__(self, company=None, api_controller=None, start_message="", media_url = ""):
        self.cache_service = CacheService()
        self.conversation_session_type = (
            api_controller.conversation_session_type 
            if api_controller and api_controller.conversation_session_type 
            else ApiController.CONVERSATION_SESSION_TYPE_TIME_BASED_SESSION
        )
        self.session_handler = SessionManager(company=company)
        if api_controller:
            self.session_obj = self.session_handler.get_session_manager_obj(api_controller.conversation_session_type)
            self.session_obj.in_memory_chat_history_service = self
            self.api_controller = api_controller
        else:
            self.session_obj = None

        self.start_message = start_message
        self.media_url = media_url
        self.exempt_keys = InMemoryMessageState.BIN_ENCODED_FIELDS

    def _get_cache_key(self, company, client_identifier):
        key_name = ""
        if self.api_controller and self.api_controller.api_route:
            key_name = f"{company.prefix}_{self.api_controller.api_route}_{client_identifier}"
        else:
            key_name = f"{company.prefix}_{client_identifier}"
        return key_name

    def _copy_cache_object(self, company, curr_client_identifier, targeted_client_identifier):
        _curr_cache_key = self._get_cache_key(company, curr_client_identifier)
        _targeted_cache_key = self._get_cache_key(company, targeted_client_identifier)
        _curr_object = self.cache_service.get(_curr_cache_key)
        self.cache_service.set(_targeted_cache_key, _curr_object)

    def _initialize_cache_structure(self, company, client_identifier, billing_session_id=''):
        """
        If cache is not found, creates required keys in the cache.
        """
        redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] No data found for client in memory.")
        cache_key = self._get_cache_key(company, client_identifier)
        temp_session_id = self.session_handler._generate_new_session_id(company=company)

        new_structure = InMemoryMessageState(
            company_id=company.id,
            billing_session_id=billing_session_id,
            session_id=temp_session_id
        ).to_dict()

        for key, value in new_structure.items():
            self.cache_service.hset(cache_key,key, value)

    def validate_conversation_session(self, company, client_identifier):
        cache_key = self._get_cache_key(company, client_identifier)
        existing_data = EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)


        if not existing_data:
            self._initialize_cache_structure(company, client_identifier)
            existing_data = EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)

        if not existing_data.get('session_id'):
            self.cache_service.hset(
                cache_key, 
                "session_id", 
                self.session_handler._generate_new_session_id(company)
            )

        if self.start_message or self.media_url:
            conversation_session_context_refresh_keyword = self.api_controller.conversation_session_refresh_keyword
            if conversation_session_context_refresh_keyword and self.start_message:
                keywords = [
                        keyword.strip().lower() 
                        for keyword in conversation_session_context_refresh_keyword.split(",")
                    ]
                start_message_words = [word.strip().lower() for word in self.start_message.split() if word.strip()]
                if len(start_message_words) == 1 and start_message_words[0] in keywords:
                    # push old session_id to queue for long term memory generation
                    if self.api_controller.is_long_term_memory_generation_enabled:
                        ltm_queue_data = LongTermMemoryQueueState(
                            company_id=company.id,
                            session_id=existing_data.get("session_id"),
                            chat_history=msgpack.unpackb(existing_data.get("chat_history")),
                            client_identifier=client_identifier,
                            vector_storage_provider=self.api_controller.vector_storage_for_long_term_memory,
                            workflow_id=self.api_controller.id,
                            workflow_name=self.api_controller.name
                        ).to_dict()
                        from chat.services.long_term_memory_generation_service import LongTermMemoryGenerationService
                        ltm_generation_service = LongTermMemoryGenerationService(company=company, api_controller=self.api_controller)
                        ltm_generation_service.push_data_to_long_term_memory_generation_queue(ltm_queue_data)
                    
                    new_session_id = self.session_handler._generate_new_session_id(company)
                    
                    success = self.cache_service.hset(cache_key, "session_id", new_session_id)
                    self.cache_service.hset(cache_key, "chat_history", msgpack.packb([]))
                    self.cache_service.hset(cache_key, "session_count", 1)
                    data = EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)
                    return data

        if self.session_obj:
            updated_data = self.session_obj.validate_and_update_session(existing_data, company, client_identifier, self.api_controller)
            for key, value in updated_data.items():
                self.cache_service.hset(cache_key, key, value)
        data_to_be_sent = EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)
        return data_to_be_sent

    def save_client_metadata(self, company, client_identifier, data):
        cache_key = self._get_cache_key(company, client_identifier)
        self.cache_service.hset(cache_key, "client_metadata", msgpack.packb(data))
        return EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)
    
    def get_client_metadata(self, company, client_identifier):
        cache_key = self._get_cache_key(company, client_identifier)
        client_metadata = self.cache_service.hget(cache_key, "client_metadata")
        return msgpack.unpackb(client_metadata) if client_metadata else {}

    def get_chat_history_from_cache(self, company, client_identifier):
        cache_key = self._get_cache_key(company, client_identifier)
        raw_chat_history = self.cache_service.hget(cache_key, "chat_history")
        
        chat_history = []
        if raw_chat_history:
            try:
                chat_history = msgpack.unpackb(raw_chat_history, raw=False)
            except Exception as e:
                redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Error in unpacking chat history (get_chat_history_from_cache) : {e}.")
                chat_history = []
        else:
            chat_history = []
        return chat_history
    
    async def save_chat_history(self, company, role, mobile, text, message_metadata, extra_save_data, client_identifier, session_validated=False):
        cache_key = self._get_cache_key(company, client_identifier)
        if not session_validated:
            new_data = self.validate_conversation_session(company, client_identifier)

        chat_history = self.get_chat_history_from_cache(company=company, client_identifier=client_identifier)

        chat_entry = LLMMessageState(
            company_id=company.id,
            role=role,
            function_name=extra_save_data.get('function_name'),
            message_metadata=message_metadata,
            text=text
        ).to_dict()

        chat_history.append(chat_entry)
        serialized_chat_history = msgpack.packb(chat_history, use_bin_type=True)

        self.cache_service.hset(cache_key, "chat_history", serialized_chat_history)

        session_count = int(self.cache_service.hget(cache_key, "session_count") or 0) + 1
        self.cache_service.hset(cache_key, "session_count", session_count)

        self.cache_service.hset(cache_key, "last_message_at", datetime.now().isoformat())
        await self._enforce_message_limit_for_conversation_context(company, cache_key, client_identifier, mobile, extra_save_data)

    def fetch_chat_history(self, company, client_identifier):
        cache_key = self._get_cache_key(company, client_identifier)
        chat_data = EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)
        if not chat_data:
            redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Fetching chat from DB.")
            self._initialize_cache_structure(company, client_identifier)
            chat_data = self._fetch_chat_from_db(company, client_identifier)

        chat_history = self.get_chat_history_from_cache(company=company, client_identifier=client_identifier)

        return chat_history

    async def _enforce_message_limit_for_conversation_context(self, company, cache_key, client_identifier, mobile, extra_save_data):
        from chat.services.conversation_manager_service import ConversationManagerService
        conversation_session_count_threshold = (
            self.api_controller.conversation_session_count
            if self.api_controller.conversation_session_count is not None
            else IN_MEMORY_CHAT_HISTORY_MESSAGE_LIMIT
        )
        session_count = int(self.cache_service.hget(cache_key, "session_count") or 0)

        enabled_summary_generation = self.api_controller.is_summary_of_chat_history_enabled
        messages_to_keep_in_chat_history_after_summarization = (
            self.api_controller.messages_to_keep_in_chat_history_after_summarization
            if self.api_controller.messages_to_keep_in_chat_history_after_summarization is not None
            else CHAT_HISTORY_MESSAGES_WITH_SUMMARY_LIMIT
        )
        summary_generation_message_count_trigger_limit = (
            self.api_controller.summary_generation_trigger_limit
            if self.api_controller.summary_generation_trigger_limit is not None
            else SUMMARY_GENERATION_TRIGGER_LIMIT
        )

        summary = ""
        chat_history = []
        if enabled_summary_generation and session_count > summary_generation_message_count_trigger_limit:
            try :
                # reducing session count to avoid summarizatin loop
                from chat.services.conversation_manager_service import ConversationManagerService
                self.cache_service.hset(cache_key, "session_count", messages_to_keep_in_chat_history_after_summarization)
                summary_generator = ConversationManagerService(company=company, api_controller=self.api_controller)
                summary = await summary_generator.generate_summary(company=company, client_identifier=client_identifier, mobile=mobile, extra_save_data=extra_save_data)
            except Exception as e:
                redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Error generating summary : {e}.")
                self.cache_service.hset(cache_key, "session_count", session_count)
                
            if summary:
                chat_history = self.get_chat_history_from_cache(company=company, client_identifier=client_identifier)
                chat_history_backup = chat_history
                try:
                    if chat_history:
                        chat_history = chat_history[-messages_to_keep_in_chat_history_after_summarization:]
                        chat_entry = LLMMessageState(
                            company_id=company.id,
                            role='system',
                            function_name=extra_save_data.get('function_name'),
                            message_metadata='',
                            text="Summary of previous conversation : " + summary
                        ).to_dict()
                        chat_history.insert(0, chat_entry)
                        self.cache_service.hset(cache_key, "chat_history", msgpack.packb(chat_history))
                except Exception as e:
                    redis_logger.add(f"[company: {company}] [client_identifier: {client_identifier}] Error adding summary to chat history : {e}.")
                    self.cache_service.hset(cache_key, "chat_history", msgpack.packb(chat_history_backup))
        elif session_count > conversation_session_count_threshold:
            chat_history = self.get_chat_history_from_cache(company=company, client_identifier=client_identifier)
            if chat_history:
                chat_history.pop(0)
                self.cache_service.hset(cache_key, "chat_history", msgpack.packb(chat_history))
                self.cache_service.hset(cache_key, "session_count", session_count - 1)

    def get_session_data(self, company, client_identifier):
        cache_key = self._get_cache_key(company, client_identifier)
        return EncodeDecodeUTF8.decode_hash(self.cache_service.cache.hgetall(cache_key), exempt_keys=self.exempt_keys)

    def _fetch_chat_from_db(self, company, client_identifier):
        CompanyUtils.set_company_registry(company=company)
        persistent_db_service = PersistentChatHistoryService()
        conversation_session_count_threshold = (
            self.api_controller.conversation_session_count
            if self.api_controller.conversation_session_count is not None
            else IN_MEMORY_CHAT_HISTORY_MESSAGE_LIMIT
        )
        db_chat_history = persistent_db_service.fetch_conversation_by_client_identifier(client_identifier, conversation_session_count_threshold, True)

        chat_data = {
            'chat_history': msgpack.packb(db_chat_history),
            'session_count': len(db_chat_history)
        }
        cache_key = self._get_cache_key(company, client_identifier)
        for key, value in chat_data.items():
            self.cache_service.hset(cache_key, key, value)
        return chat_data

    def _refresh_chat_after_keyword(self, chat_history, chat_data, conversation_session_context_refresh_keyword):
        keywords = [
            keyword.strip().lower() 
            for keyword in conversation_session_context_refresh_keyword.split(",")
        ]
        latest_hello_index = next(
            (index for index in range(len(chat_history) - 1, -1, -1)
            if chat_history[index].get("role") == "user" and 
            any(keyword in chat_history[index].get("content", "").lower() for keyword in keywords)),
            None
        )
        if latest_hello_index is not None:
            chat_history = chat_history[latest_hello_index:]

        return chat_history
    
    def clear_chat_history(self, company, client_identifier):

        cache_key = self._get_cache_key(company, client_identifier)
        self.cache_service.hset(cache_key, "chat_history", msgpack.packb([]))
        self.cache_service.hset(cache_key, "session_count", 0)
        return EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(cache_key), exempt_keys=self.exempt_keys)
    
    def _handle_inactivity(self, existing_data, company, client_identifier, api_controller):
        conversation_session_time_threshold = (
            api_controller.conversation_session_time
            if api_controller.conversation_session_time is not None
            else IN_MEMORY_CHAT_HISTORY_TIME_LIMIT
        )
        last_message_at = existing_data.get("last_message_at")
        if last_message_at:
            last_message_time = datetime.fromisoformat(last_message_at)
            time_difference = (datetime.now() - last_message_time).total_seconds() / 60

            if time_difference > conversation_session_time_threshold:
                if self.api_controller.is_long_term_memory_generation_enabled:
                        ltm_queue_data = LongTermMemoryQueueState(
                            company_id=company.id,
                            session_id=existing_data.get("session_id"),
                            chat_history=msgpack.unpackb(existing_data.get("chat_history")),
                            client_identifier=client_identifier,
                            vector_storage_provider=self.api_controller.vector_storage_for_long_term_memory,
                            workflow_id=self.api_controller.id,
                            workflow_name=self.api_controller.name
                        ).to_dict()
                        from chat.services.long_term_memory_generation_service import LongTermMemoryGenerationService
                        ltm_generation_service = LongTermMemoryGenerationService(company=company, api_controller=self.api_controller)
                        ltm_generation_service.push_data_to_long_term_memory_generation_queue(ltm_queue_data)
                self.clear_chat_history(company, client_identifier)
                self.cache_service.hset(self._get_cache_key(company, client_identifier), "session_id", self.session_handler._generate_new_session_id(company))
                self.cache_service.hset(self._get_cache_key(company, client_identifier), "last_message_at", datetime.now().isoformat())

        return EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(self._get_cache_key(company, client_identifier)), exempt_keys=self.exempt_keys)

    def _handle_message_limit_per_session(self, existing_data, company, client_identifier, api_controller):
        total_message_count = int(existing_data.get("session_count", 0))

        conversation_session_count_threshold = (
            api_controller.conversation_session_count
            if api_controller.conversation_session_count is not None
            else IN_MEMORY_CHAT_HISTORY_MESSAGE_LIMIT
        )
        if total_message_count > conversation_session_count_threshold:
            if self.api_controller.is_long_term_memory_generation_enabled:
                        ltm_queue_data = LongTermMemoryQueueState(
                            company_id=company.id,
                            session_id=existing_data.get("session_id"),
                            chat_history=msgpack.unpackb(existing_data.get("chat_history")),
                            client_identifier=client_identifier,
                            vector_storage_provider=self.api_controller.vector_storage_for_long_term_memory,
                            workflow_id=self.api_controller.id,
                            workflow_name=self.api_controller.name
                        ).to_dict()
                        from chat.services.long_term_memory_generation_service import LongTermMemoryGenerationService
                        ltm_generation_service = LongTermMemoryGenerationService(company=company, api_controller=self.api_controller)
                        ltm_generation_service.push_data_to_long_term_memory_generation_queue(ltm_queue_data)
            self.clear_chat_history(company, client_identifier)
            self.cache_service.hset(self._get_cache_key(company, client_identifier), "session_id", self.session_handler._generate_new_session_id(company))

        return EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(self._get_cache_key(company, client_identifier)), exempt_keys=self.exempt_keys)