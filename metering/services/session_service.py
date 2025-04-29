from datetime import datetime
from backend.services.cache_service import CacheService
from basics.utils import EncodeDecodeUTF8, Registry, generate_random_string
from backend.constants import CURRENT_USER_ID, CURRENT_API_COMPANY
from api_controller.models import ApiController
from datetime import datetime, timedelta
from chat.states.In_memory_message_state import InMemoryMessageState
import msgpack



class SessionManager:

    def __init__(self, company=None):
        self.company = company if company else Registry().get(CURRENT_API_COMPANY)
        self.temp_session_id = f"{self.company.prefix}-{self.company.id}-{int(datetime.now().timestamp())}-{generate_random_string(8)}"
        self.SESSION_OBJ_CHOICES = {
            ApiController.BILLING_SESSION_TYPE_PER_CALL_ONE_SESSION: BillingSessionManager.PerCallOneSession(
                company=company),
            ApiController.BILLING_SESSION_TYPE_TIME_BASED_SESSION: BillingSessionManager.TimeBasedSession(
                company=company),
            ApiController.BILLING_SESSION_TYPE_TOKEN_BASED_SESSION: BillingSessionManager.TokenBasedSession(
                company=company),
            ApiController.BILLING_SESSION_TYPE_COUNT_AND_TIME_BASED_SESSION: BillingSessionManager.TimeAndCountBasedSession(
                company=company),

            # conversation manager
            ApiController.CONVERSATION_SESSION_TYPE_TIME_BASED_SESSION: ConversationSessionManager.TimeBasedConversationSession(
                company=company),
            ApiController.CONVERSATION_SESSION_TYPE_COUNT_BASED_SESSION: ConversationSessionManager.CountBasedConversationSession(
                company=company),
            ApiController.CONVERSATION_SESSION_TYPE_TIME_AND_COUNT_BASED_SESSION: ConversationSessionManager.TimeAndCountBasedConversationSession(
                company=company)
        }

        self.cache_service = CacheService()

    def get_session_manager_obj(self, session_type):
        session_obj = self.SESSION_OBJ_CHOICES.get(session_type, None)
        return session_obj

    def generate_session(self, session_type=None, api_controller=None, session_id=None, content=None):
        session_obj = self.SESSION_OBJ_CHOICES.get(session_type, None)
        if not session_id:
            return self.temp_session_id, self.temp_session_id
        elif not session_obj:
            return session_id, self.temp_session_id
        return session_obj.generate_session(api_controller, session_id, self.temp_session_id, content)

    def validate_session_id(self, api_controller=None, session_id=None, check_count=False, check_time=False):
        _target_count = api_controller.billing_session_count if api_controller.billing_session_count else 10
        _target_time = api_controller.billing_session_time if api_controller.billing_session_time else 30
        """ time must be in minutes """
        session = self.get_session(session_id)
        if not session:
            return False, None
        elif check_count and check_time:
            _count = int(session.get("billing_session_count")) if session.get("billing_session_count") else 0
            _billing_session_id = session.get("billing_session_id")
            _session_started_at = session.get("session_start_at")
            if _session_started_at:
                _session_started_at = datetime.fromisoformat(_session_started_at)
            if _count < _target_count and _session_started_at > (datetime.now() - timedelta(minutes=_target_time)):
                self.set_session(_count + 1, session_id, _billing_session_id)
                return True, _billing_session_id
        return False, None

    def reset_cache_session(self, session_id=None, billing_session_id=None):
        self.set_session(0, session_id, billing_session_id, reset=True)

    def get_session_key(self, session_id):
        return f"{self.company.prefix}_{session_id}"

    def get_session(self, session_id):
        _session_key = self.get_session_key(session_id)
        return EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(_session_key), InMemoryMessageState.BIN_ENCODED_FIELDS)

    def set_session(self, count, session_id, billing_session_id, reset=False):
        _session_key = self.get_session_key(session_id)
        session = EncodeDecodeUTF8.decode_hash(self.cache_service.hgetall(_session_key), InMemoryMessageState.BIN_ENCODED_FIELDS)

        if reset or not session:
            session_value = InMemoryMessageState(
                billing_session_count=count,
                billing_session_id=billing_session_id,
                session_start_at=datetime.now().isoformat(),
                company_id=self.company.id,
                session_id=session.get("session_id","") if session else "",
                session_count=session.get("session_count",0) if session else 0,
                last_message_at=session.get("last_message_at","") if session else "",
                chat_history=session.get("chat_history", msgpack.packb([])) if session else msgpack.packb([]),
                client_metadata=session.get("client_metadata", msgpack.packb({})) if session else msgpack.packb({})
            ).to_dict()
            for key, value in session_value.items():
                self.cache_service.hset(_session_key, key, value)
        else:
            self.cache_service.hset(_session_key, "billing_session_count", count)
            self.cache_service.hset(_session_key, "billing_session_id", billing_session_id)

    def generate_session_id(self, **kwargs):
        company = Registry().get(CURRENT_API_COMPANY)
        session_id = f"{company.id}_{int(datetime.now().timestamp())}"
        return session_id

    def _generate_new_session_id(self, company):
        return f"{company.prefix}-{company.id}-{int(datetime.now().timestamp())}-{generate_random_string(8)}"


class BillingSessionManager(SessionManager):
    def __init__(self):
        pass

    class PerCallOneSession(SessionManager):

        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def generate_session(self, api_controller, session_id, temp_session_id, content):
            return session_id, temp_session_id

    class TimeBasedSession(SessionManager):

        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def generate_session(self, api_controller, session_id, temp_session_id, content):
            return session_id, temp_session_id

    class TokenBasedSession(SessionManager):

        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def generate_session(self, api_controller, session_id, temp_session_id, content):
            return session_id, temp_session_id

    class TimeAndCountBasedSession(SessionManager):

        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def generate_session(self, api_controller, session_id, temp_session_id, content):
            if isinstance(content, str):
                if content.lower() in ["hi", "hello"]:
                    self.reset_cache_session(session_id=session_id, billing_session_id=temp_session_id)
                    return session_id, temp_session_id
                else:
                    is_valid_session, billing_session_id = self.validate_session_id(api_controller=api_controller,
                                                                                    session_id=session_id,
                                                                                    check_count=True,
                                                                                    check_time=True)
                    if is_valid_session:
                        return session_id, billing_session_id
                    else:
                        """ if session is not valid initiating a new session"""
                        self.reset_cache_session(session_id, temp_session_id)
                        return session_id, temp_session_id
            return session_id, temp_session_id


class ConversationSessionManager(SessionManager):
    def __init__(self) -> None:
        pass
    """
    Todo: Conversation sessions must be created with in this class only, 
    - create a function to add new session entry in conversation sessions here only
    - update conversation session function should also be a part of this class only
    """

    class TimeBasedConversationSession(SessionManager):
        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def validate_and_update_session(self, existing_data, company, client_identifier, api_controller):
            existing_data = self.in_memory_chat_history_service._handle_inactivity(existing_data, company,
                                                                                   client_identifier, api_controller)
            return existing_data

    class CountBasedConversationSession(SessionManager):
        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def validate_and_update_session(self, existing_data, company, client_identifier, api_controller):
            existing_data = self.in_memory_chat_history_service._handle_message_limit_per_session(existing_data,
                                                                                                  company,
                                                                                                  client_identifier,
                                                                                                  api_controller)

            return existing_data

    class TimeAndCountBasedConversationSession(SessionManager):
        def __init__(self, company=None):
            self.company = company
            self.cache_service = CacheService()

        def validate_and_update_session(self, existing_data, company, client_identifier, api_controller):
            existing_data = self.in_memory_chat_history_service._handle_inactivity(existing_data, company,
                                                                                   client_identifier, api_controller)
            existing_data = self.in_memory_chat_history_service._handle_message_limit_per_session(existing_data,
                                                                                                  company,
                                                                                                  client_identifier,
                                                                                                  api_controller)
            return existing_data