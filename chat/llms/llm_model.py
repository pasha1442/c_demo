# from langchain_community.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage, FunctionMessage
from langchain_community.callbacks.manager import get_openai_callback
from typing import List, Dict, Any, Optional
import os
import json
from langchain_google_vertexai import ChatVertexAI
import vertexai
from dotenv import load_dotenv
import requests

load_dotenv()
class LlmModel:
    def __init__(self):
        OPENAI_API_KEY = os.getenv('OPEN_AI_KEY')
        self.api_key = OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPEN_AI_KEY environment variable is not set")

    def preProcessMessages(self, llm: str, prompt: str, chat_history: List[Dict[str, str]]):
        messages = None
        if(llm == "openai"):
            system_prompt = SystemMessage(content=prompt)
            messages = [system_prompt]
            for message in reversed(chat_history):
                if message['role'] != 'system':
                    if message['role'] == 'function':
                        messages.append((FunctionMessage(name = 'function_name', content=message['content'])))
                    else :
                        messages.append((message['role'], message['content']))
        elif llm == "google":
            system_prompt = SystemMessage(content=prompt)
            messages = [system_prompt]
            
            prev_role = None
            prev_content = ""
            print(chat_history)
            for message in reversed(chat_history):
                if message['role'] != 'system':
                    if message['role'] == prev_role:
                        prev_content = prev_content + "\n" + message['content']
                    else:
                        if prev_role:
                            if prev_role == 'function':
                                messages.append((FunctionMessage(name = 'designated_to_other_assistant_by_assistant_manager', content=prev_content))) # type: ignore
                            elif prev_role == "user":
                                messages.append(HumanMessage(content=prev_content)) # type: ignore
                            elif prev_role == "assistant":
                                messages.append(AIMessage(content=prev_content)) # type: ignore
                        
                        prev_role = message['role']
                        prev_content = message['content']
            # print(messages)
            # Add the last message
            if prev_role:
                if prev_role == "user":
                    messages.append(HumanMessage(content=prev_content)) # type: ignore
                elif prev_role == "assistant":
                    messages.append(AIMessage(content=prev_content)) # type: ignore
        elif llm == "mistral":
            # system_prompt = SystemMessage(content=prompt)
            
            messages = [{"role": "system", "content": prompt}]
            prev_role = None
            prev_content = ""
            for message in reversed(chat_history):
                if message['role'] != 'system':
                    if prev_role == message['role']:
                        prev_content += "\n"+message['content']
                    else:
                        
                        if prev_role == 'function':    
                            messages.append({'role':prev_role, 'content':prev_content, "name": "function_1"})
                        elif prev_role:
                            messages.append({'role':prev_role, 'content':prev_content})
                        prev_role = message['role']
                        prev_content = message['content']
            if prev_role:
                if prev_role == 'function':    
                    messages.append({'role':prev_role, 'content':prev_content, "name": "function_1"})
                else:
                    messages.append({'role':prev_role, 'content':prev_content})
            

        return messages

    def postProcessLocalLLMResponse(self, data):
        ai_message = AIMessage(
            content=data['content'],
            additional_kwargs=data['additional_kwargs'],
            response_metadata=data['response_metadata'],
            id=data['id'],
            usage_metadata=data['usage_metadata']
        )

        return ai_message

    def process_request(self, request: str, llm: str, prompt: str, functions: Optional[List[Dict[str, Any]]], model: str, chat_history: List[Dict[str, str]]):

        messages = self.preProcessMessages(llm, prompt, chat_history)

        chat = None
        if(llm == "openai"):
            print("OpenAI Model")
            chat = ChatOpenAI(temperature=0, model=model, openai_api_key=self.api_key)
        elif llm == "google":
            print("GOOGLE MODEL")
            
            vertexai.init(project='kl-ecom-comm-prod', location="us-central1")
            # os.environ["GOOGLE_APPLICATION_CREDENTIALS"] ="/home/auriga/AurigaWork/KindlifeCB/application_default_credentials.json"
            chat = ChatVertexAI(model_name="gemini-pro", temperature=0.2, project='kl-ecom-comm-prod', location="us-central1")
        
        elif llm == "mistral":
            print("Mistral Model")

            url = os.getenv("LOCAL_MODEL_URL")
            tools = []
            for function in functions:
                tools.append({"type": "function", "function": function})
            
            # messages[0]["content"] = messages[0]["content"] + f"""\nQuery: {chat_history}\nAvailable Functions: {tools}"""
            print("MESSAGES******************")
            print(messages)
            print("********************")
            # print(tools)
            payload = {
                "functions": tools,
                "chat_history": messages
            }
            # print(messages)
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                response = self.postProcessLocalLLMResponse(response.json())
                
                return response
            else:
                print("Failed to call API:", response.status_code, response.text)
                return []

        with get_openai_callback() as cb:
            if functions:
                response = chat.invoke(messages, functions = functions)
            else:
                response = chat.invoke(messages)
            
            print(f"Total Tokens: {cb.total_tokens}")
            print(f"Prompt Tokens: {cb.prompt_tokens}")
            print(f"Completion Tokens: {cb.completion_tokens}")
            print(f"Total Cost (USD): ${cb.total_cost}")
        
        return response

    def process_master_response(self, response):
        master_response = {}
        if response.additional_kwargs.get('function_call'):
            function_call = response.additional_kwargs['function_call']
            function_name = function_call['name']
            function_arguments = json.loads(function_call['arguments'])
            
            assistant_mapping = {
                "designate_to_order_assistant": "order assistant",
                "designate_to_expert_assistant": "expert assistant",
                "designate_to_brand_support_assistant": "brand assistant",
                "designate_to_corporate_gifting_support_assistant": "corporate gifting assistant",
                "designate_to_bulk_order_support_assistant": "bulk order assistant",
                "designate_to_policy_expert_assistant": "policy expert assistant"
            }
            
            assistant = assistant_mapping.get(function_name, "other assistant")
            
            master_response['message'] = f"designated to {assistant} by assistant manager"
            master_response['is_function'] = True
            master_response['function_name'] = function_name
            master_response['arguments'] = function_arguments
            master_response['role'] = "system"
        
        if response.content:
            master_response['message'] = response.content
        
        return master_response

    def process_response(self, response):
        assistant_response = {}
        if response.additional_kwargs.get('function_call'):
            function_call = response.additional_kwargs['function_call']
            function_name = function_call['name']
            function_arguments = json.loads(function_call['arguments'])
            
            assistant_response['message'] = "function"
            assistant_response['is_function'] = True
            assistant_response['function_name'] = function_name
            assistant_response['arguments'] = function_arguments
            assistant_response['role'] = "system"
        
        if response.content:
            assistant_response['completion'] = response.content

        return assistant_response
