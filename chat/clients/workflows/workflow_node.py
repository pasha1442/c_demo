import asyncio
from langchain_core.messages import AIMessage, ToolMessage
from chat.assistants import get_active_prompt_from_langfuse
from chat.clients.workflows import all_tools
from langfuse.decorators import observe, langfuse_context #type:ignore
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from chat.llms.google import Google
from chat.llms.local import Local
from chat.llms.openai import Openai
from chat.clients.workflows.agent_state import PipelineState
from backend.logger import Logger
from chat.services.workflow_attribute_manager.workflow_attribute_service import WorkflowAttributeService

workflow_logger = Logger(Logger.WORKFLOW_LOG)

class WorkflowLlmNode:
    
    def __init__(self, name, tools, prompt_name, include_in_final_response, response_schema=None):
        
        self.name = name
        self.tools = tools
        self.prompt_name = prompt_name
        self.include_in_final_response = include_in_final_response
        self.response_schema = response_schema
        
        

    # @observe()
    def execute(self, state):
        
        print(f"\n{self.name} is working...")
        workflow_logger.add(f"\n{self.name} is working...")

        context_obj = PipelineState.get_workflow_context_object_from_state(state)
        llm_info = get_active_prompt_from_langfuse(context_obj.company.id, self.prompt_name)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="messages")
            ]
        ).partial(system_prompt=llm_info["system_prompt"])

        chat = self.get_llm_class(llm_info["llm"])
        
        last_message = state["messages"][-1]
        if isinstance(last_message, ToolMessage):
            return_direct = getattr(all_tools, last_message.name).return_direct
            if return_direct:
                return {
                            "messages": [AIMessage(content=last_message.content, additional_kwargs={}, name=self.name)],
                            "sender": self.name, 
                            "workflow_context": state["workflow_context"],
                            "include": self.include_in_final_response,
                            "llm_info": llm_info
                        }
        
        response_schema_content = None
        if self.response_schema:
            response_schema_content = WorkflowAttributeService(company=context_obj.company).get_workflow_attribute_by_name(self.response_schema).first()['content']
        
        result = asyncio.run(chat.process_request(state, prompt, llm_info, self.tools, context_obj.company.name, context_obj.session_id, response_schema_content))
        
        workflow_logger.add(f"Workflow Node: {self.name} | Session: [{context_obj.session_id}] | [{context_obj.company}] | LLM Response: {result}")

        return {
                "messages": [AIMessage(**result.dict(exclude={"type", "name"}), name=self.name)],
                "sender": self.name, 
                "workflow_context": state["workflow_context"],
                "include": self.include_in_final_response,
                "llm_info": llm_info,
                "response_format_schema": self.response_schema
            }
        
    def get_llm_class(self, llm):
        llm_classes = {
            "openai": Openai,
            "google": Google,
            "open source": Local
        }

        return llm_classes.get(llm.lower(), Openai)()
    