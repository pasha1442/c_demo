from basics.custom_exception import WorkflowExecutorException
from .base import BaseLLM
import vertexai # type: ignore
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory # type: ignore
from decouple import config
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)

class Google(BaseLLM):
    
    def __init__(self):
        super().__init__()
        self.google_credential_project_name = config("GOOGLE_CREDENTIAL_PROJECT_NAME")
        self.google_credential_location = config("GOOGLE_CREDENTIAL_PROJECT_LOCATION")
        
        if not self.google_credential_location or not self.google_credential_project_name:
            workflow_logger.add("Vertex ai credentials environment variable is not set")
            raise ValueError("Vertex ai credentials environment variable is not set")

        vertexai.init(project=self.google_credential_project_name, location=self.google_credential_location)
    
    async def process_request(self, state, prompt, llm_info, tools, company_name, session_id, response_schema_content=None):
        
        if state and 'messages' in state:
            state["messages"] = self.preProcessMessages(state["messages"])
        else:
            state = {"messages": []} 
        
        temperature = llm_info['temperature'] if llm_info['temperature'] else self.temperature
        safety_settings = {
                HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        llm = ChatVertexAI(model_name=llm_info["model"], temperature=temperature, project=self.google_credential_project_name, location=self.google_credential_location, safety_settings=safety_settings)
        
        if tools:
            llm_chain = prompt | llm.bind_tools(tools)
        else :
            llm_chain = prompt | llm

        # langfuse_handler = langfuse_context.get_current_langchain_handler()
        try:
            result = await llm_chain.ainvoke(state)

        except Exception as e:
            workflow_logger.add(f"Gemini call error | Session: {session_id} | Company : {company_name} | Unable to get response from llm {llm_info['model']} | Error: {e}")
            raise WorkflowExecutorException(f"Gemini call error | Session: {session_id} | Company : {company_name} | Unable to get response from llm {llm_info['model']} | Error: {e}")
        
        return result
