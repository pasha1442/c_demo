from datetime import datetime
from typing import List, Optional
import msgpack

class InMemoryMessageState:

    BIN_ENCODED_FIELDS = {"chat_history","client_metadata"}

    def __init__(
        self,
        company_id: int,
        session_start_at: Optional[str] = None,
        last_message_at: Optional[str] = None,
        billing_session_id: str = "",
        session_id : str = "",
        billing_session_count: int = 0,
        session_count: int = 0,
        chat_history: Optional[List[dict]] = None,
        client_metadata : dict = None
    ):
        self.session_start_at = session_start_at or datetime.now().isoformat()
        self.last_message_at = last_message_at or ""
        self.billing_session_id = billing_session_id
        self.session_id = session_id
        self.billing_session_count = billing_session_count
        self.session_count = session_count
        self.chat_history = chat_history or msgpack.packb([])
        self.company_id = company_id
        self.client_metadata = client_metadata or msgpack.packb({})

    def to_dict(self) -> dict:
        """Convert the object to a dictionary."""
        return {
            "session_start_at": self.session_start_at,
            "last_message_at" : self.last_message_at,
            "billing_session_id": self.billing_session_id,
            "session_id" : self.session_id,
            "billing_session_count" : self.billing_session_count,
            "session_count": self.session_count,
            "chat_history": self.chat_history,
            "company_id": self.company_id,
            "client_metadata" : self.client_metadata
        }
