import json
from typing import Dict, List
from langchain_core.messages import AIMessage, ToolMessage

class BaseLLM:
    def __init__(self) -> None:
        self.temperature = 0
        self.max_tokens = 500
    
    def preProcessMessages(self, chat_history: List[Dict[str, str]]):
        messages = []
        prev_role = None
        prev_content = ""
        for message in chat_history:
            if isinstance(message, AIMessage) or isinstance(message, ToolMessage):
                role = "assistant"
            else:
                role = "user"
            content = message.content

            if prev_role is None and role != 'user':
                continue

            if prev_role == role:
                prev_content += "\n"+content
            else:
                if prev_role:
                    messages.append({'role':prev_role, 'content':prev_content})

                prev_role = role
                prev_content = content
        if prev_role:
            messages.append({'role':prev_role, 'content':prev_content})

        if messages[-1]['role'] == "assistant":
            tool_message = messages[-1]
            messages = messages[:-1]
            messages[-1]['content'] += "\nTool response: \n" + tool_message['content']

        return messages
    
    def process_request(self, state, prompt, llm_info, tools, company_name):
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def process_tool_response(self, result, llm_info):
        if 'tool_calls' in result.additional_kwargs:
            for tool in result.additional_kwargs['tool_calls']:
                if tool['function']['name'] == 'knowledge_retriver':
                    arguments = json.loads(tool['function']['arguments'])
                    arguments['data_source'] = llm_info["data_source"]
                    tool['function']['arguments'] = json.dumps(arguments)
            
            for tool in result.tool_calls:
                if tool['name'] == 'knowledge_retriver':
                    tool['args']['data_source'] =  llm_info["data_source"]
                    
        return result