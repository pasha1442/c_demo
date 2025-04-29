import os
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass
from google.oauth2 import service_account
from django.conf import settings
from google.cloud import aiplatform
import vertexai
from vertexai.preview.generative_models import GenerativeModel, GenerationConfig
from langchain_google_vertexai import VertexAI
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence
from langchain_community.callbacks.manager import get_openai_callback
from langchain_community.callbacks.tracers import ConsoleCallbackHandler
from ..langchain_service import LangchainService
import json

logger = logging.getLogger(__name__)

# Default configurations
DEFAULT_MODEL = "gemini-1.5-flash"  # Updated to use correct model name
DEFAULT_GENERATION_CONFIG = {
    "temperature": 0.7,
    "max_output_tokens": 8000,  # Just under Vertex AI's limit of 8192
    "top_p": 0.9,
    "top_k": 40  # Must be between 1 and 41 (exclusive)
}

# Model-specific configurations
MODEL_CONFIGS = {
    "gemini-1.5-flash": {  # Fast model for quick responses
        "max_top_k": 40,
        "max_output_tokens": 8000,
        "supports_vision": False,
        "description": "Fastest model, best for quick responses",
        "latency_optimized": True
    },
    "gemini-pro": {
        "max_top_k": 40,
        "max_output_tokens": 8000,
        "supports_vision": False,
        "description": "Most capable text model, best for complex tasks"
    },
    "gemini-pro-vision": {
        "max_top_k": 40,
        "max_output_tokens": 8000,
        "supports_vision": True,
        "description": "Vision-capable model for image analysis"
    }
}

@dataclass
class ServiceStatus:
    is_running: bool = False
    model_loaded: bool = False
    last_checked: datetime = None
    error: str = None
    model_info: Dict = None

class VertexAIService:
    
    def __init__(self, model_name: str = DEFAULT_MODEL, generation_config: Optional[Dict[str, Any]] = None, company=None, session_id=None):
        """Initialize the Vertex AI service with specified model
        
        Args:
            model_name: Name of model to use (e.g. gemini-1.5-pro)
            generation_config: Optional custom generation config
            company: Company object for tracing
            session_id: Session ID for tracing
        """
        self.status = ServiceStatus()
        self.company = company
        self.session_id = session_id
        # self.service
        
        # Project Configuration from environment variables with defaults
        self.project_id = os.getenv('GOOGLE_CREDENTIAL_PROJECT_NAME')
        self.location = os.getenv('GOOGLE_CREDENTIAL_LOCATION', 'us-central1')
        
        if not self.project_id:
            error_msg = "GOOGLE_CREDENTIAL_PROJECT_NAME not set in environment"
            self._handle_error(error_msg, "critical", "Configuration Error")
            raise ValueError(error_msg)
        
        # Model Configuration
        if model_name not in MODEL_CONFIGS:
            error_msg = f"Unsupported model: {model_name}. Must be one of: {list(MODEL_CONFIGS.keys())}"
            self._handle_error(error_msg, "critical", "Configuration Error")
            raise ValueError(error_msg)
            
        self.base_model = model_name
        self.model_name = self.base_model  # Gemini models don't need project/location in path
        
        # Validate and set generation configuration
        self.generation_config = self._validate_generation_config(
            generation_config or DEFAULT_GENERATION_CONFIG.copy(),
            model_name
        )
        
        # Get credentials path from environment
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not credentials_path:
            error_msg = "GOOGLE_APPLICATION_CREDENTIALS environment variable not set"
            self._handle_error(error_msg, "critical", "Authentication Error")
            raise ValueError(error_msg)
        
        # Initialize credentials
        self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
        
        # Initialize Vertex AI
        vertexai.init(
            project=self.project_id,
            location=self.location,
            credentials=self.credentials
        )
        
        # Initialize Langchain service and model with tracing
        self._init_models()
        
        # Update status with complete model info
        self.status.is_running = True
        self.status.model_loaded = True
        self.status.model_info = {
            "timestamp": datetime.now().isoformat(),
            "model": self.base_model,
            "model_path": self.model_name,
            "project_id": self.project_id,
            "location": self.location,
            "generation_config": self.generation_config,
            "capabilities": MODEL_CONFIGS[self.base_model]
        }
        
        logger.info(f"✅ Successfully initialized Vertex AI with model: {self.base_model}")

    def _validate_generation_config(self, config: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Validate and adjust generation config based on model constraints
        
        Args:
            config: Generation configuration to validate
            model_name: Name of the model to validate against
            
        Returns:
            Validated and adjusted configuration
        """
        model_config = MODEL_CONFIGS[model_name]
        
        # Validate top_k
        if config.get("top_k"):
            config["top_k"] = min(config["top_k"], model_config["max_top_k"])
            
        # Validate max_output_tokens
        if config.get("max_output_tokens"):
            config["max_output_tokens"] = min(
                config["max_output_tokens"],
                model_config["max_output_tokens"]
            )
            
        return config

    def _init_models(self):
        """Initialize Langchain with specified model and tracing"""
        try:
            # Set up logging level to suppress verbose output
            logging.getLogger('langchain').setLevel(logging.WARNING)
            
            # Create Vertex AI model through Langchain with correct token limits
            model_config = MODEL_CONFIGS[self.base_model]
            self.generation_config["max_output_tokens"] = min(
                self.generation_config.get("max_output_tokens", 2048),
                model_config["max_output_tokens"]
            )
            
            self.llm = VertexAI(
                model_name=self.base_model,
                project=self.project_id,
                location=self.location,
                credentials=self.credentials,
                verbose=False,  # Disable verbose output
                **self.generation_config
            )
            
            # Store model reference for backwards compatibility
            self.model = self.llm
            
            # Initialize Langchain service with company for tracing
            self.langchain_service = LangchainService(
                company=self.company,
                session_id=self.session_id,
                trace_name="Data Enricher"
            )
            self.langchain_service.set_llm(self.llm)
            
            logger.info(f"✅ Successfully initialized Langchain with model: {self.base_model}")
            logger.info(f"   Generation config: {self.generation_config}")
            
        except Exception as e:
            error_msg = f"Error initializing Langchain model: {str(e)}"
            self._handle_error(error_msg, "critical", "Model Initialization Error")
            raise

    def process_batch(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """Process a batch of prompts using Langchain"""
        if not self.status.is_running or not self.status.model_loaded:
            error_msg = "Service not initialized"
            return [self._create_error_response(error_msg, "critical", "Service not initialized")] * len(prompts)
            
        responses = []
        for prompt in prompts:
            try:
                # Add JSON validation instruction to prompt
                enhanced_prompt = f"{prompt}\n\nIMPORTANT: Ensure the response is a complete and valid JSON object. Do not truncate or leave any JSON objects incomplete."
                
                # Run through Langchain with tracing
                response = self.langchain_service.run_chain(
                    "default_chain",
                    {
                        "input": enhanced_prompt,
                        "metadata": {
                            "session_id": self.session_id,
                            "model": self.base_model,
                            "model_path": self.model_name,
                            "project_id": self.project_id,
                            "location": self.location,
                            "generation_config": self.generation_config,
                            "company_id": self.company.id if self.company else None,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                )
                print(f"✅ Vertex AI Printing Response: {response}")
                # Handle response based on standardized format
                if isinstance(response, dict) and "error" in response:
                    responses.append(self._create_error_response(
                        response["error"],
                        response.get("error_type", "unknown"),
                        response.get("raw_error", "Unknown error")
                    ))
                else:
                    # Validate response is complete JSON
                    response_text = response.get("response", "")
                    try:
                        # Try to parse as JSON to ensure it's complete
                        json.loads(response_text)
                        responses.append({
                            "response": response_text,
                            "metadata": {
                                "session_id": self.session_id,
                                "timestamp": datetime.now().isoformat(),
                                "model": self.base_model,
                                "model_path": self.model_name,
                                "project_id": self.project_id,
                                "location": self.location,
                                "generation_config": self.generation_config,
                                "capabilities": MODEL_CONFIGS[self.base_model]
                            }
                        })
                    except json.JSONDecodeError as je:
                        # If JSON is incomplete, retry with a smaller batch
                        responses.append(self._create_error_response(
                            "Incomplete JSON response",
                            "non_critical",
                            f"JSON validation failed: {str(je)}"
                        ))
                    
            except Exception as e:
                responses.append(self._create_error_response(
                    str(e),
                    "non_critical",
                    str(e)
                ))
                
        return responses

    def check_health(self) -> Tuple[bool, str]:
        """Check if Vertex AI is properly configured and accessible"""
        self.status.last_checked = datetime.now()
        
        if not self.status.is_running or not self.status.model_loaded:
            error_msg = "Service not initialized"
            self._handle_error(error_msg, "critical", "Service not initialized")
            return False, error_msg

        try:
            # Try to create a model instance to verify access
            model = VertexAI(
                model_name=self.base_model,
                project=self.project_id,
                location=self.location,
                credentials=self.credentials
            )
            return True, "Service is healthy"
        except Exception as e:
            error_msg = f"Error checking Vertex AI status: {str(e)}"
            self._handle_error(error_msg, "critical", str(e))
            return False, str(e)

    def set_model(self, model_name: str, generation_config: Optional[Dict[str, Any]] = None) -> bool:
        """Switch to a different model with optional configuration update
        
        Args:
            model_name: Name of the model to switch to (e.g. gemini-pro-vision)
            generation_config: Optional new generation config
        """
        try:
            if model_name not in MODEL_CONFIGS:
                error_msg = f"Unsupported model: {model_name}. Must be one of: {list(MODEL_CONFIGS.keys())}"
                self._handle_error(error_msg, "critical", "Configuration Error")
                return False
                
            # Update model configuration
            self.base_model = model_name
            self.model_name = self.base_model
            
            # Validate and update generation config
            if generation_config:
                self.generation_config = self._validate_generation_config(
                    generation_config,
                    model_name
                )
            
            # Reinitialize models with new configuration
            self._init_models()
            
            # Update status with complete model info
            self.status.model_info.update({
                "timestamp": datetime.now().isoformat(),
                "model": self.base_model,
                "model_path": self.model_name,
                "generation_config": self.generation_config,
                "capabilities": MODEL_CONFIGS[self.base_model]
            })
            
            logger.info(f"Successfully switched to model: {model_name}")
            return True
            
        except Exception as e:
            error_msg = f"Error switching to model {model_name}: {str(e)}"
            self._handle_error(error_msg, "critical", str(e))
            return False

    def _handle_error(self, error_msg: str, error_type: str = "critical", raw_error: str = None):
        """Handle and log errors with proper classification
        
        Args:
            error_msg: Human-readable error message
            error_type: Either "critical" or "non_critical"
            raw_error: Original error for debugging
        """
        logger.error(error_msg)
        self.status.error = error_msg
        if error_type == "critical":
            self.status.is_running = False

    def _create_error_response(self, error_msg: str, error_type: str, raw_error: str) -> Dict[str, Any]:
        """Create standardized error response following the established format"""
        return {
            "error": error_msg,
            "error_type": error_type,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "model": self.base_model,
                "model_path": self.model_name,
                "project_id": self.project_id,
                "location": self.location,
                "generation_config": self.generation_config
            },
            "raw_error": raw_error
        }

    def list_available_models(self) -> Dict[str, Any]:
        """List all available models in the current project and location"""
        try:
            print("\n=== Available Vertex AI Models ===")
            
            aiplatform.init(project=self.project_id, location=self.location)
        
            # Test: List models in Vertex AI
            print("Fetching available models in Vertex AI...")
            models = aiplatform.Model.list()
            
            if not models:
                print("No models found in Vertex AI. Your credentials and setup are working, but no models exist.")
            else:
                print("Models available in Vertex AI:")
                print("\n\n")
                for model in models:
                    print(f" - {model.display_name} (ID: {model.resource_name})")
                print("\n\n")
        except Exception as e:
            error_msg = f"Error listing available models: {str(e)}"
            error_result = self._handle_error(error_msg, "critical", str(e))
            return error_result