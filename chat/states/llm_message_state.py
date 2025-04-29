import json

class LLMMessageState:
    def __init__(self, 
                company_id=None, 
                role='user',
                function_name='',
                message_metadata='',
                text='', 
            ):
        self.company_id = company_id
        self.role = role
        self.function_name = function_name
        self.message_metadata = message_metadata
        self.text = text

    def to_dict(self):
        """
        Returns a structured dictionary representing the chat entry.
        """
        if self.role == 'function' and self.function_name:
            return {
                'role': self.role,
                'name': self.function_name,
                'content': self.text,
                'message_metadata': self.message_metadata
            }
        else:
            return {
                'role': self.role,
                'content': self.text,
                'message_metadata': self.message_metadata
            }

    def to_json(self):
        """
        Converts the structured dictionary to a JSON string.
        """
        return json.dumps(self.to_dict())