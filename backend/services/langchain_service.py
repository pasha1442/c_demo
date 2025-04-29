import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from django.conf import settings
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence
from langchain.schema.language_model import BaseLanguageModel
from langchain.chains import SequentialChain, SimpleSequentialChain
from langchain.memory import ConversationBufferMemory
from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
from langchain_community.callbacks.manager import get_openai_callback
from backend.logger import Logger

logger = Logger(Logger.INFO_LOG)

# Default tracing configuration
ENABLE_LANGFUSE_TRACING = True  # Can be overridden via environment variable
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

class LangchainService:
    """A service for managing Langchain operations independent of specific LLM implementations"""
    
    def __init__(self, company=None, session_id=None, trace_name=None):
        """Initialize LangchainService with optional company for tracing
        
        Args:
            company: Company object containing Langfuse credentials
        """
        self.chains = {}
        self.llm = None
        self.memories = {}
        self.session_id = session_id
        self.company = company
        self.enable_tracing = os.getenv("ENABLE_LANGFUSE_TRACING", True)
        
        # Initialize Langfuse tracing if company credentials are available
        if self.enable_tracing and company and company.langfuse_public_key and company.langfuse_secret_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = company.langfuse_public_key
            os.environ["LANGFUSE_SECRET_KEY"] = company.langfuse_secret_key
            os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        
        # Set up logging level to suppress verbose output
        logging.getLogger('langchain').setLevel(logging.WARNING)
        
    def set_llm(self, llm: BaseLanguageModel) -> None:
        """Set the LLM to be used by this service"""
        self.llm = llm
        
    def create_prompt_template(self, template: str, input_variables: Optional[List[str]] = None) -> PromptTemplate:
        """Create a prompt template with optional input variables"""
        try:
            if input_variables is None:
                return PromptTemplate.from_template(template)
            return PromptTemplate(template=template, input_variables=input_variables)
        except Exception as e:
            logger.add(f"Error creating prompt template: {str(e)}")
            raise

    def create_chain(self, 
                    name: str,
                    prompt_template: Union[str, PromptTemplate],
                    memory: bool = False,
                    input_variables: Optional[List[str]] = None) -> bool:
        """Create a named chain with optional memory"""
        if not self.llm:
            logger.add("LLM not initialized")
            return False

        try:
            # Create prompt template if string provided
            if isinstance(prompt_template, str):
                prompt_template = self.create_prompt_template(prompt_template, input_variables)
            
            # Setup memory if requested
            chain_memory = None
            if memory:
                chain_memory = ConversationBufferMemory()
                self.memories[name] = chain_memory
            
            # Create the chain with tracing if enabled
            chain = prompt_template | self.llm
            if self.enable_tracing and self.company:
                try:
                    trace_handler = LangfuseCallbackHandler(
                        public_key=self.company.langfuse_public_key,
                        secret_key=self.company.langfuse_secret_key,
                        host=LANGFUSE_HOST
                    )
                    chain = chain.with_config({"callbacks": [trace_handler]})
                except Exception as e:
                    logger.add(f"Failed to initialize Langfuse tracing for company ID {self.company.id}: {str(e)}")
            
            self.chains[name] = chain
            return True
            
        except Exception as e:
            logger.add(f"Error creating chain '{name}': {str(e)}")
            return False

    def create_sequential_chain(self, 
                              name: str,
                              chain_names: List[str],
                              simple: bool = True) -> bool:
        """Create a sequential chain from existing chains"""
        try:
            # Get the component chains
            component_chains = [self.chains[chain_name] for chain_name in chain_names]
            
            # Create either a simple or regular sequential chain with tracing
            if simple:
                chain = SimpleSequentialChain(chains=component_chains)
            else:
                chain = SequentialChain(chains=component_chains)
            
            # Add tracing if enabled
            if self.enable_tracing and self.company:
                try:
                    trace_handler = LangfuseCallbackHandler(
                        public_key=self.company.langfuse_public_key,
                        secret_key=self.company.langfuse_secret_key,
                        host=LANGFUSE_HOST
                    )
                    chain = chain.with_config({"callbacks": [trace_handler]})
                except Exception as e:
                    logger.add(f"Failed to initialize Langfuse tracing for company ID {self.company.id}: {str(e)}")
            
            self.chains[name] = chain
            return True
            
        except Exception as e:
            logger.add(f"Error creating sequential chain '{name}': {str(e)}")
            return False

    def run_chain(self, name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run a named chain with inputs and tracing
        
        Args:
            name: Name of the chain to run
            inputs: Dictionary of inputs for the chain
            
        Returns:
            Dictionary containing response and metadata
        """
        if name not in self.chains:
            error_msg = f"Chain '{name}' not found"
            return self._create_error_response(error_msg, "critical")
            
        try:
            # Extract metadata if provided
            metadata = inputs.pop("metadata", {}) if isinstance(inputs, dict) else {}
            session_id = metadata.get("session_id")
            request_name = metadata.get("request_name")
            print("-----------------------------Langfuse Tracing-------------------------")
            # Create Langfuse trace
            config = {}
            if self.enable_tracing and self.company:
                try:
                    trace_handler = LangfuseCallbackHandler(
                        trace_name=f"{request_name}_trace",
                        session_id=session_id,
                        metadata={
                            "company_id": str(self.company.id),
                            "chain_name": name,
                            **metadata
                        }
                    )
                    config = {"callbacks": [trace_handler]}
                except Exception as e:
                    logger.error(f"Failed to initialize Langfuse tracing: {e}")
            
            # Run chain with tracing
            chain = self.chains[name]
            response = chain.invoke(
                inputs,
                config=config
            )
            
            return {
                "response": response,
                "metadata": {
                    "chain_name": name,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    **metadata
                }
            }
            
        except Exception as e:
            error_msg = f"Error running chain '{name}': {str(e)}"
            return self._create_error_response(error_msg, "non_critical", str(e))

    def get_memory(self, chain_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get the conversation memory for a chain if it exists"""
        if chain_name in self.memories:
            return self.memories[chain_name].chat_memory.messages
        return None

    def clear_memory(self, chain_name: str) -> bool:
        """Clear the memory for a specific chain"""
        if chain_name in self.memories:
            self.memories[chain_name].clear()
            return True
        return False

    def _create_error_response(self, error_msg: str, error_type: str, raw_error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "error": error_msg,
            "error_type": error_type,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "tracing_enabled": self.enable_tracing
            },
            "raw_error": raw_error
        }