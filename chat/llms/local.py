from basics.custom_exception import WorkflowExecutorException
from .base import BaseLLM
from typing import List, Dict, Optional, List, Any
from langchain.schema import AIMessage
from langchain_openai import ChatOpenAI
import os
import json
import re
from langfuse.decorators import langfuse_context  # type:ignore
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)


class Local(BaseLLM):

    def __init__(self) -> None:
        super().__init__()

    def process_request(self, state, prompt, llm_info, tools, company_name):
        state["messages"] = self.preProcessMessages(state["messages"])

        url = os.getenv("LOCAL_MODEL_URL")
        temperature = llm_info['temperature'] if llm_info['temperature'] else self.temperature
        max_tokens = llm_info['max_tokens'] if llm_info['max_tokens'] else self.max_tokens
        llm = ChatOpenAI(model=llm_info["model"], openai_api_key="EMPTY", openai_api_base=url, max_tokens=max_tokens,
                         temperature=temperature)
        if tools:
            llm_chain = prompt | llm.bind_tools(tools)
        else:
            llm_chain = prompt | llm

        langfuse_handler = langfuse_context.get_current_langchain_handler()
        try:
            result = llm_chain.invoke(state, config={"callbacks": [langfuse_handler]})
        except Exception as e:
            workflow_logger.add(f"Error: {e}")
            raise WorkflowExecutorException(
                f"Company : {company_name} | Unable to get response from llm {llm_info['model']} | Error: {e}")

        response = self.postProcessResponse(result, llm_info)
        return response

    def postProcessResponse(self, response, llm_info):
        try:
            pattern = r'\[{"name":.*?}\]'
            match = re.search(pattern, response.content)
            function = {}
            if match:
                json_string = match.group(0)
                json_data = json.loads(json_string)
                function['id'] = "id_1"
                function['type'] = "function"
                function["function"] = {}
                function['function']["name"] = json_data[0]["name"]
                function['function']['arguments'] = json.dumps(json_data[0]['arguments'])
                response.additional_kwargs['tool_calls'] = []
                response.additional_kwargs['tool_calls'].append(function)

                tool_call = {}
                tool_call['name'] = function['function']['name']
                tool_call['args'] = json.loads(function['function']['arguments'])
                tool_call['id'] = function['id']
                tool_call['type'] = 'tool_call'
                response.tool_calls.append(tool_call)
                response.content = ""

            response = self.process_tool_response(response, llm_info)
            return response
        except Exception as e:
            print(f"Error: {e}")
            return response
