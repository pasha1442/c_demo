import asyncio
import json
from typing import Optional
from basics.custom_exception import WorkflowExecutorException
from .base import BaseLLM
from langchain_openai import ChatOpenAI
from decouple import config # type: ignore
from langfuse.decorators import langfuse_context  # type: ignore
from backend.logger import Logger
from pydantic import BaseModel, Field
from langchain_core.utils.function_calling import (
    convert_to_openai_function
)
from langchain_openai.chat_models.base import (
    _convert_to_openai_response_format
)

workflow_logger = Logger(Logger.WORKFLOW_LOG)


class Openai(BaseLLM):
    def __init__(self):
        super().__init__()
        OPENAI_API_KEY = config('OPEN_AI_KEY')
        self.api_key = OPENAI_API_KEY
        if not self.api_key:
            workflow_logger.add("OPEN_AI_KEY environment variable is not set")
            raise ValueError("OPEN_AI_KEY environment variable is not set")
        
        self.base_json_schema = {
            "name": "json_schema",
            "description": "This is the schema you  need to follow to give responses.",
            "strict": True,
            "schema": {}
        }
        
                        
    async def process_request(self, state, prompt, llm_info, tools, company_name, session_id, response_schema_content=None):

        temperature = llm_info['temperature'] if llm_info['temperature'] else self.temperature
        
        
        if response_schema_content:
            response_schema_content = self.convert_to_openai_schema(json.loads(response_schema_content))
            self.base_json_schema["schema"] = response_schema_content
            llm = ChatOpenAI(temperature=temperature, model=llm_info['model'], openai_api_key=self.api_key, response_format={"type": "json_schema", "json_schema":  self.base_json_schema})
        else:
            llm = ChatOpenAI(temperature=temperature, model=llm_info['model'], openai_api_key=self.api_key)
        
        if tools:
            if response_schema_content:
                llm_chain = prompt | llm.bind_tools(tools, strict=True)
            else:
                llm_chain = prompt | llm.bind_tools(tools)
        else :
            llm_chain = prompt | llm
            
        # llm_chain = llm_chain.with_config(tags=["final_node"])
        # langfuse_handler = langfuse_context.get_current_langchain_handler()
        """Adding try catch in case llm node is unable to execute."""
        try:
            result = await llm_chain.ainvoke(state)
        except Exception as e:
            workflow_logger.add(f"Openai call error | Session: {session_id} | Company : {company_name} | Unable to get response from llm {llm_info['model']} | Error: {e}")
            raise WorkflowExecutorException(f"Openai call error | Session: {session_id} | Company : {company_name} | Unable to get response from llm {llm_info['model']} | Error: {e}")
        
        result = self.process_tool_response(result, llm_info)
        return result
    
    async def llm_call(self, chain, langfuse_handler, state):
        
        result = await chain.ainvoke(state, config={"callbacks": [langfuse_handler]})
        return result
    
    def convert_to_openai_schema(self, data, name="ResponseFormatSchema", description="Auto-generated OpenAI response format schema"):
        """Recursively parse JSON data to extract schema properties."""
        if isinstance(data, dict):
            return {
                "type": "object",
                "properties": {key: self.convert_to_openai_schema(value) for key, value in data.items()},
                "additionalProperties": False,
                "required": list(data.keys())
            }
        elif isinstance(data, list):
            if data:  # Assume homogeneous lists, infer from first element
                return {"type": "array", "items": self.convert_to_openai_schema(data[0])}
            else:
                return {"type": "array", "items": {}}
        elif isinstance(data, str):
            return {"type": "string"}
        elif isinstance(data, int):
            return {"type": "integer"}
        elif isinstance(data, float):
            return {"type": "number"}
        elif isinstance(data, bool):
            return {"type": "boolean"}
        elif data is None:
            return {"type": "null"}
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")