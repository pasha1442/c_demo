
class DynamicHookState:

    def __init__(
        self,
        company_id: int,
        session_id : str = "",
        api_route: str = "",
        hook_type: str = "",
        client_identifier: str = ""
    ):
        self.api_route = api_route
        self.hook_type = hook_type
        self.session_id = session_id
        self.company_id = company_id
        self.client_identifier = client_identifier
    
    def to_dict(self) -> dict:
        """Convert the object to a dictionary."""
        return {
            "company_id": self.company_id,
            "client_identifier": self.client_identifier,
            "session_id": self.session_id,
            "api_route": self.api_route,
            "hook_type": self.hook_type,
        }