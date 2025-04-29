from datetime import datetime
import msgpack
import json
from typing import List, Optional, Any


class LongTermMemoryQueueState:
    """
    State of the data pushed to a queue for long-term memory generation.
    """

    def __init__(
        self,
        company_id: int,
        session_id: str,
        chat_history: Optional[List[dict]] = None,
        client_identifier: str = "",
        vector_storage_provider: str = "",
        workflow_id: str = "",
        workflow_name: str = "",
        created_at : Optional[float] = None
    ):
        self.company_id = company_id
        self.session_id = session_id
        self.client_identifier = client_identifier
        self.vector_storage_provider = vector_storage_provider
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name

        if created_at is None:
            self.created_at = datetime.now().timestamp()
        else:
            self.created_at = created_at

        if chat_history is None:
            self.chat_history = []
        elif isinstance(chat_history, bytes):
            self.chat_history = msgpack.unpackb(chat_history, raw=False)
        else:
            self.chat_history = chat_history

    def to_dict(self) -> dict:
        data = {
            "company_id": self.company_id,
            "session_id": self.session_id,
            "client_identifier": self.client_identifier,
            "chat_history" : self.chat_history,
            "vector_storage_provider" : self.vector_storage_provider,
            "workflow_name" : self.workflow_name,
            "workflow_id" : self.workflow_id,
            "created_at" : self.created_at
        }
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
