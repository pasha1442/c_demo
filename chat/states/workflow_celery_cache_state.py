import json
from datetime import datetime
from typing import List, Optional


class WorkflowCeleryCacheState:

    def __init__(
            self,
            company_id: str,
            client_identifier: str,
            thread_start_at: Optional[str] = None,
            execution_time: Optional[str] = None,
            messages: Optional[List[dict]] = None,
    ):
        self.client_identifier = client_identifier
        self.thread_start_at = thread_start_at or datetime.now().isoformat()
        self.execution_time = execution_time or datetime.now().isoformat()
        self.messages = messages or []
        self.company_id = company_id

    def to_dict(self) -> dict:
        """Convert the object to a dictionary."""
        return {
            "company_id": self.company_id,
            "client_identifier": self.client_identifier,
            "thread_start_at": self.thread_start_at,
            "execution_time": self.execution_time,
            "messages": self.messages,
            "company_id": self.company_id,
        }


