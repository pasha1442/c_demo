"""Service for handling data enrichment operations"""
import os
import json
import math
import asyncio
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from requests import request

import pandas as pd
from django.conf import settings
from django.utils import timezone
from django.core.files import File
from asgiref.sync import sync_to_async

from backend.logger import Logger
from data_processing.models import DataEnrichment, DataEnrichmentPartition, DataIngestion, DataIngestionPartition
from backend.services.llm.vertex_ai_service import VertexAIService, MODEL_CONFIGS
from backend.services.llm.ollama_service import OllamaService
from backend.services.llm.open_ai_service import OpenAIService
from backend.services.langchain_service import LangchainService
from backend.services.langfuse_service import LangfuseService
from company.utils import CompanyUtils

# Constants
BATCH_SIZE_MIN = 10
BATCH_SIZE_MAX = 1000
BATCH_SIZE_DEFAULT = 100
PARALLEL_EXECUTION_COUNT = 5  # Number of partitions to process in parallel

logger = Logger(Logger.INFO_LOG)

class BaseDataEnricher(ABC):
    def __init__(self):
        self.company = None
        self.session_id = None
        self.request_name = None
        self.service = None
        self.config = {}

    def setup(self, company=None, session_id=None, request_name=None):
        """Set up the enricher with company and session info"""
        self.company = company
        self.session_id = session_id
        self.request_name = request_name
        print("----------------Setting up enricher--------------------")
        if company:
            self.initialize_langchain()
            print(f"✅ Initialized enricher for company {company.id}")
        
        return self

    def initialize_langchain(self):
        """Initialize Langchain service with company credentials if available"""
        if not self.company:
            print("⚠️ No company provided, skipping Langchain initialization")
            return
        
        try:
            # Initialize Langchain service with company context
            print("------Initialize Langchain service with company context-----")
            langchain_service = LangchainService(
                company=self.company,
                session_id=self.session_id,
                trace_name=self.request_name
            )
            
            # Set the LLM from the existing service
            if hasattr(self.service, 'llm'):
                langchain_service.set_llm(self.service.llm)
                
                # Create chain with request name
                if self.request_name:
                    success = langchain_service.create_chain(
                        name=self.request_name,
                        prompt_template="{input}",
                        memory=False,
                        input_variables=["input"]
                    )
                    
                    if not success:
                        raise Exception(f"Failed to create chain '{self.request_name}'")
                else:
                    # Create default chain as fallback
                    success = langchain_service.create_chain(
                        name="default_chain",
                        prompt_template="{input}",
                        memory=False,
                        input_variables=["input"]
                    )
                    
                    if not success:
                        raise Exception("Failed to create default chain")
            
            # Store the langchain service
            self.service.langchain_service = langchain_service
            print(f"✅ Initialized Langchain service for company {self.company.id}")
            if self.request_name:
                print(f"   Chain created: {self.request_name}")
            
        except Exception as e:
            error_msg = f"Failed to initialize Langchain service: {str(e)}"
            print(f"❌ {error_msg}")
            logger.add(error_msg)
            raise

    def check_health(self):
        """Check if the enricher is healthy"""
        try:
            if not self.service:
                raise ValueError("Service not initialized")
                
            # Check service health
            health_status, health_info = self.service.check_health()
            if not health_status:
                raise ValueError(f"Service health check failed: {health_info}")
                
            # Check Langchain service if available
            if hasattr(self.service, 'langchain_service'):
                health_status, health_info = self.service.langchain_service.check_health()
                if not health_status:
                    raise ValueError(f"Langchain service health check failed: {health_info}")
            
            return True, "All services healthy"
            
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            print(f"❌ {error_msg}")
            logger.add(error_msg)
            return False, error_msg

    def get_model_name(self):
        """Get the model name for this enricher"""
        raise NotImplementedError("Subclasses must implement get_model_name")

    def process_data(self, data: Dict[str, Any], prompt_template: str) -> Dict[str, Any]:
        """Process data using the enricher"""
        try:
            # Validate company context
            if not self.company:
                raise ValueError("Company context not initialized")
            
            # Validate input data
            if not isinstance(data, dict):
                raise ValueError("Input data must be a dictionary")
            if "data" not in data:
                raise ValueError("Input data must contain 'data' key")
            if not prompt_template:
                raise ValueError("Input data must contain 'prompt_template' key")
                
            # Get metadata
            metadata = data.get("metadata", {})
            
            # Format prompt with data
            try:
                # Properly escape special characters in the JSON string
                batch_json = json.dumps(data.get("data", []), 
                    indent=2,
                    ensure_ascii=False,  # Preserve non-ASCII characters
                    default=str  # Handle non-serializable objects
                )
                print("\n" + "="*60)
                print("🔄 PROCESSING BATCH")
                print("="*60)
                print(f"\n📄 Batch JSON Preview:")
                print(f"   Length: {len(batch_json)} chars")
                print(f"   First 200 chars: {batch_json[:200]}...")
                print(f"   Records: {len(data.get('data', []))}")
                print("="*60 + "\n")
                prompt = prompt_template.replace("{batch_data}", batch_json)
            except Exception as e:
                return {
                    "error": f"Failed to serialize batch data: {str(e)}",
                    "error_type": "critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": str(e)
                }

            # Process the prompt using service
            if hasattr(self.service, 'langchain_service'):
                result = self.service.langchain_service.run_chain(
                    "default_chain",
                    {
                        "input": prompt,
                        "metadata": {
                            **metadata,
                            "company_id": str(self.company.id),
                            "session_id": self.session_id,
                            "request_name": self.request_name
                        }
                    }
                )
            else:
                print("\n🔄 Printing Generating response...", prompt)
                result = self.service.generate_response(prompt)
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "error": result["error"],
                    "error_type": result.get("error_type", "non_critical"),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": str(result)
                }
            
            # Ensure response follows Vertex AI format
            if isinstance(result, dict):
                response_text = result.get('response', str(result))
                metadata = result.get('metadata', {})
            else:
                response_text = str(result)
                metadata = {}
                
            return {
                "response": response_text,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model": self.service.model_name,
                    "model_path": metadata.get('model_path'),
                    "project_id": self.service.project_id,
                    "location": self.service.location,
                    "generation_config": self.config,
                    "company_id": str(self.company.id),
                    "session_id": self.session_id
                },
                "error_type": None,
                "raw_response": str(result)
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "error_type": "critical",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "model": self.service.model_name,
                    "project_id": self.service.project_id,
                    "location": self.service.location,
                    "generation_config": self.config,
                    "company_id": str(self.company.id),
                    "session_id": self.session_id
                },
                "raw_error": str(e)
            }

    @classmethod
    def get_enricher(cls, model_name: str) -> 'BaseDataEnricher':
        """Get the appropriate enricher based on the model name"""
        if model_name == DataEnrichment.LLM_MODEL_CHOICE_OLLAMA_MISTRAL:
            return OllamaEnricher()
        elif model_name == DataEnrichment.LLM_MODEL_CHOICE_OPENAI_GPT_3_5:
            return OpenAIEnricher()
        elif model_name == DataEnrichment.LLM_MODEL_CHOICE_VERTEX_AI_MISTRAL:
            return VertexAIMistralEnricher()
        elif model_name == DataEnrichment.LLM_MODEL_CHOICE_VERTEX_AI_GEMINI_1_5_FLASH:
            return VertexAIGeminiEnricher()
        else:
            raise ValueError(f"Unknown model name: {model_name}")

class OpenAIEnricher(BaseDataEnricher):
    def __init__(self):
        super().__init__()
        print("\n🤖 Using OpenAI GPT-3.5 Enricher for data processing")
        self.service = OpenAIService()
        self.config = {
            "temperature": 0.7,
            "max_tokens": 1024,
            "top_p": 0.9,
            "model": "gpt-3.5-turbo"
        }

    def check_health(self) -> Tuple[bool, str]:
        return self.service.check_health()

    def get_model_name(self) -> str:
        return DataEnrichment.LLM_MODEL_CHOICE_OPENAI_GPT_3_5

    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data using OpenAI service"""
        try:
            prompt = data.get("prompt", "")
            request = data.get("request")
            partition = data.get("partition")
            partition_data = data.get("partition_data", {})

            if not prompt:
                return {
                    "error": "Empty prompt provided",
                    "error_type": "critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.config["model"],
                        "generation_config": self.config
                    },
                    "raw_error": "Empty prompt provided"
                }

            # Process the prompt using service
            if hasattr(self.service, 'langchain_service'):
                result = self.service.langchain_service.run_chain(
                    "default_chain",
                    {
                        "input": prompt,
                        "metadata": {
                            "request_id": str(request.id) if request else None,
                            "partition_id": partition.id if partition else None,
                            "record_count": len(partition_data.get('data', [])) if partition_data else 0,
                            "session_id": self.session_id,
                            "company_id": str(self.company.id) if self.company else None
                        }
                    }
                )
            else:
                print("\n🔄 Printing Generating response...", prompt)
                print("\n🔄 Generating response... with ", self.service)
                result = self.service.generate_response(prompt)
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "error": result["error"],
                    "error_type": result.get("error_type", "non_critical"),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.config["model"],
                        "generation_config": self.config
                    },
                    "raw_error": str(result)
                }
            
            # Ensure response follows standardized format
            if isinstance(result, dict):
                response_text = result.get('response', str(result))
                metadata = result.get('metadata', {})
            else:
                response_text = str(result)
                metadata = {}
                
            return {
                "response": response_text,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model": self.config["model"],
                    "model_path": metadata.get('model_path'),
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "error_type": None,
                "raw_response": str(result)
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "error_type": "critical",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "model": self.config["model"],
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "raw_error": str(e)
            }

class OllamaEnricher(BaseDataEnricher):
    def __init__(self):
        super().__init__()
        print("\n🤖 Using Ollama Mistral Enricher for data processing")
        self.service = OllamaService()
        self.config = {
            "temperature": 0.7,
            "max_tokens": 1024,
            "top_p": 0.9,
            "model": "mistral"
        }

    def check_health(self) -> Tuple[bool, str]:
        return self.service.check_health()

    def get_model_name(self) -> str:
        return DataEnrichment.LLM_MODEL_CHOICE_OLLAMA_MISTRAL

    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data using Ollama service"""
        try:
            prompt = data.get("prompt", "")
            request = data.get("request")
            partition = data.get("partition")
            partition_data = data.get("partition_data", {})

            if not prompt:
                return {
                    "error": "Empty prompt provided",
                    "error_type": "critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.config["model"],
                        "generation_config": self.config
                    },
                    "raw_error": "Empty prompt provided"
                }

            # Process the prompt using service
            if hasattr(self.service, 'langchain_service'):
                result = self.service.langchain_service.run_chain(
                    "default_chain",
                    {
                        "input": prompt,
                        "metadata": {
                            "request_id": str(request.id) if request else None,
                            "partition_id": partition.id if partition else None,
                            "record_count": len(partition_data.get('data', [])) if partition_data else 0,
                            "session_id": self.session_id,
                            "company_id": str(self.company.id) if self.company else None
                        }
                    }
                )
            else:
                result = self.service.generate_response(prompt)
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "error": result["error"],
                    "error_type": result.get("error_type", "non_critical"),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.config["model"],
                        "generation_config": self.config
                    },
                    "raw_error": str(result)
                }
            
            # Ensure response follows standardized format
            if isinstance(result, dict):
                response_text = result.get('response', str(result))
                metadata = result.get('metadata', {})
            else:
                response_text = str(result)
                metadata = {}
                
            return {
                "response": response_text,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model": self.config["model"],
                    "model_path": metadata.get('model_path'),
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "error_type": None,
                "raw_response": str(result)
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "error_type": "critical",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "model": self.config["model"],
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "raw_error": str(e)
            }

class VertexAIMistralEnricher(BaseDataEnricher):
    
    def __init__(self):
        super().__init__()
        print("\n🤖 Using Vertex AI Mistral Enricher for data processing")
        
        # Initialize service with appropriate model name
        vertex_model = "gemini-1.5-pro"
        print(f"🔄 Initializing VertexAI with model: {vertex_model}")
        
        # Get model-specific configuration limits
        model_limits = MODEL_CONFIGS.get(vertex_model, MODEL_CONFIGS[vertex_model])
        
        # Validate and prepare generation config
        self.config = {
            "temperature": 0.7,
            "max_output_tokens": 8000,  # Just under Vertex AI's limit of 8192
            "top_p": 0.9,
            "top_k": 40,  # Must be between 1 and 41 (exclusive)
            "supports_vision": model_limits.get("supports_vision", False)
        }
        
        # Ensure config respects model limits
        self.config["max_output_tokens"] = 8000  # Just under Vertex AI's limit of 8192
        self.config["top_k"] = 40  # Must be between 1 and 41 (exclusive)
        
        # Initialize service with model and config
        self.service = VertexAIService(
            model_name=vertex_model,
            generation_config=self.config
        )
        
        # Check service health
        health_status, health_info = self.service.check_health()
        if not health_status:
            error_msg = f"Vertex AI service health check failed: {health_info}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
            
        print(f"✅ Successfully initialized VertexAI service with model: {vertex_model}")
        print(f"   Generation config: {self.config}")
        print(f"   Model capabilities: {model_limits}")

    def check_health(self) -> Tuple[bool, str]:
        return self.service.check_health()

    def get_model_name(self) -> str:
        return DataEnrichment.LLM_MODEL_CHOICE_VERTEX_AI_MISTRAL

    def process_data(self, data: Dict[str, Any], prompt_template: str) -> Dict[str, Any]:
        """Process data using Vertex AI service"""
        try:
            print("\n" + "="*60)
            print("🔄 PROCESSING BATCH IN VERTEX AI MISTRAL")
            print("="*60)
            
            # Validate input data
            batch_data = data.get("data", [])
            if not batch_data:
                error_msg = "No data provided for processing"
                print(f"\n❌ {error_msg}")
                return {
                    "error": error_msg,
                    "error_type": "critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": "Empty batch data"
                }
            
            print(f"\n📊 Batch Statistics:")
            print(f"   Records: {len(batch_data)}")
            if batch_data:
                print(f"   Sample Keys: {list(batch_data[0].keys())}")
            
            # Format prompt with data
            try:
                # Properly escape special characters in the JSON string
                batch_json = json.dumps(batch_data, 
                    indent=2,
                    ensure_ascii=False,  # Preserve non-ASCII characters
                    default=str  # Handle non-serializable objects
                )
                print(f"\n📄 Batch JSON Preview:")
                print(f"   Length: {len(batch_json)} chars")
                print(f"   First 200 chars: {batch_json[:200]}...")
                
                # Replace placeholder in prompt template
                prompt = prompt_template.replace("{batch_data}", batch_json)
                print(f"\n📝 Prompt Preview:")
                print(f"   Length: {len(prompt)} chars")
                print(f"   First 200 chars: {prompt[:200]}...")
                
            except Exception as e:
                error_msg = f"Failed to serialize batch data: {str(e)}"
                print(f"\n❌ {error_msg}")
                return {
                    "error": error_msg,
                    "error_type": "critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": str(e)
                }

            # Process the prompt using service
            print("\n🤖 Processing with Vertex AI...")
            if hasattr(self.service, 'langchain_service'):
                result = self.service.langchain_service.run_chain(
                    "default_chain",
                    {
                        "input": prompt,
                        "metadata": {
                            "request_id": str(data.get("request_id")),
                            "batch_size": len(batch_data),
                            "session_id": self.session_id,
                            "company_id": str(self.company.id) if self.company else None
                        }
                    }
                )
            else:
                result = self.service.generate_response(prompt)
            
            print("\n✅ Response received from Vertex AI")
            
            # Handle error response
            if isinstance(result, dict) and "error" in result:
                print("\n❌ Error in Vertex AI response:")
                print(f"   Error: {result['error']}")
                print(f"   Type: {result.get('error_type', 'unknown')}")
                return {
                    "error": result["error"],
                    "error_type": result.get("error_type", "non_critical"),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": str(result)
                }
            
            # Extract response from Vertex AI format
            if isinstance(result, dict):
                response_text = result.get('response', '')
                metadata = result.get('metadata', {})
            else:
                response_text = str(result)
                metadata = {}
            
            # Validate response
            if not response_text:
                error_msg = "Empty response from Vertex AI"
                print(f"\n❌ {error_msg}")
                return {
                    "error": error_msg,
                    "error_type": "non_critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": str(result)
                }
            
            print("\n🔍 Validating response format...")
            try:
                # Parse the response to ensure it's valid JSON
                parsed_response = json.loads(response_text)
                if not isinstance(parsed_response, list):
                    parsed_response = [parsed_response]
                
                # Validate we got back the same number of records
                if len(parsed_response) != len(batch_data):
                    print(f"\n⚠️ Warning: Response count ({len(parsed_response)}) doesn't match input ({len(batch_data)})")
                
                # Re-serialize to ensure consistent format
                response_text = json.dumps(parsed_response, ensure_ascii=False)
                print(f"\n✅ Response validated:")
                print(f"   Records: {len(parsed_response)}")
                print(f"   Size: {len(response_text)} bytes")
                
            except json.JSONDecodeError as e:
                print(f"\n⚠️ Warning: Response is not valid JSON, using as raw text")
                print(f"   Error: {str(e)}")
                print(f"   Preview: {response_text[:200]}...")
            
            # Return standardized response
            return {
                "response": response_text,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model": self.service.model_name,
                    "model_path": metadata.get('model_path'),
                    "project_id": self.service.project_id,
                    "location": self.service.location,
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id,
                    "batch_size": len(batch_data),
                    "response_size": len(response_text)
                }
            }
            
        except Exception as e:
            error_msg = f"Failed to process batch: {str(e)}"
            print(f"\n❌ {error_msg}")
            return {
                "error": error_msg,
                "error_type": "critical",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "model": self.service.model_name,
                    "project_id": self.service.project_id,
                    "location": self.service.location,
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "raw_error": str(e)
            }

class VertexAIGeminiEnricher(BaseDataEnricher):
    
    def __init__(self):
        super().__init__()
        print("\n🤖 Using Vertex AI Gemini Flash Enricher for data processing")
        
        # Initialize service with appropriate model name
        vertex_model = "gemini-1.5-flash"
        print(f"🔄 Initializing VertexAI with model: {vertex_model}")
        
        # Get model-specific configuration limits
        model_limits = MODEL_CONFIGS.get(vertex_model, MODEL_CONFIGS[vertex_model])
        
        # Validate and prepare generation config
        self.config = {
            "temperature": 0.7,
            "max_output_tokens": 8000,  # Just under Vertex AI's limit of 8192
            "top_p": 0.9,
            "top_k": 40,  # Must be between 1 and 41 (exclusive)
            "supports_vision": model_limits.get("supports_vision", False),
            "latency_optimized": True
        }
        
        # Ensure config respects model limits
        self.config["max_output_tokens"] = 8000  # Just under Vertex AI's limit of 8192
        self.config["top_k"] = 40  # Must be between 1 and 41 (exclusive)
        
        # Initialize service with model and config
        self.service = VertexAIService(
            model_name=vertex_model,
            generation_config=self.config
        )
        print("----------------------here 1122----------------------")
        # Check service health
        health_status, health_info = self.service.check_health()
        if not health_status:
            error_msg = f"Vertex AI service health check failed: {health_info}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
            
        print(f"✅ Successfully initialized VertexAI service with model: {vertex_model}")
        print(f"   Generation config: {self.config}")
        print(f"   Model capabilities: {model_limits}")

    def check_health(self) -> Tuple[bool, str]:
        return self.service.check_health()

    def get_model_name(self) -> str:
        return DataEnrichment.LLM_MODEL_CHOICE_VERTEX_AI_GEMINI_1_5_FLASH

    def process_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data using Vertex AI service"""
        try:
            prompt = data.get("prompt_template", "")
            request = data.get("request")
            partition = data.get("partition")
            partition_data = data.get("partition_data", {})
            
            if not prompt:
                return {
                    "error": "Empty prompt provided",
                    "error_type": "critical",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": "Empty prompt provided"
                }
            prompt = prompt.replace(
                "{batch_data}",
                json.dumps(data.get("data", []), indent=2)
            )
            # print("- Printing Final Prompt:", prompt)
            # Process the prompt using service
            print("=-------------------Langchain Service-------------------=")
            if hasattr(self.service, 'langchain_service'):
                print("-------------------Langchain Service-------------------")
                result = self.service.langchain_service.run_chain(
                    self.request_name,
                    {
                        "input": prompt,
                        "metadata": {
                            "request_name": self.request_name,
                            "request_id": str(request.id) if request else None,
                            "partition_id": partition.id if partition else None,
                            "record_count": len(partition_data.get('data', [])) if partition_data else 0,
                            "session_id": self.session_id,
                            "company_id": str(self.company.id) if self.company else None
                        }
                    }
                )
            else:
                result = self.service.generate_response(prompt)
            
            if isinstance(result, dict) and "error" in result:
                return {
                    "error": result["error"],
                    "error_type": result.get("error_type", "non_critical"),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "model": self.service.model_name,
                        "project_id": self.service.project_id,
                        "location": self.service.location,
                        "generation_config": self.config
                    },
                    "raw_error": str(result)
                }
            
            # Ensure response follows Vertex AI format
            if isinstance(result, dict):
                response_text = result.get('response', str(result))
                metadata = result.get('metadata', {})
            else:
                response_text = str(result)
                metadata = {}
                
            return {
                "response": response_text,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model": self.service.model_name,
                    "model_path": metadata.get('model_path'),
                    "project_id": self.service.project_id,
                    "location": self.service.location,
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "error_type": None,
                "raw_response": str(result)
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "error_type": "critical",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "model": self.service.model_name,
                    "project_id": self.service.project_id,
                    "location": self.service.location,
                    "generation_config": self.config,
                    "company_id": str(self.company.id) if self.company else None,
                    "session_id": self.session_id
                },
                "raw_error": str(e)
            }

class DataEnricherService:

    def __init__(self):
        self.langfuse_service = None
        self.status_metadata_instance_json = {
            "is_processed": False,
            "processed_at": "",
            "input_file_name":"",
            "output_file_path":"",
            "input_file_path":"",
            "total_records": 0,
            "successful_records": 0,
            "failed_records": 0,
            "error":""
        }

    async def _update_completion_percentage(self, request: DataEnrichment) -> None:
        """Update completion percentage based on partition status"""
        try:
            # Get partition counts
            total_partitions = await sync_to_async(request.get_total_partitions_count)()
            if total_partitions == 0:
                return
            
            # Get processed partitions (both successful and failed)
            processed_partitions = await sync_to_async(request.get_processed_partitions_count)()
            failed_partitions = await sync_to_async(request.get_failed_partitions_count)()
            total_processed = processed_partitions + failed_partitions
            
            # Calculate percentage
            percentage = int((total_processed / total_partitions) * 100)
            
            # Set company context for database operations
            print(f"Company ID: {request.company} |  Completion Percentage: {percentage} %")
            CompanyUtils.set_company_registry(request.company)
            
            # Update request
            await sync_to_async(DataEnrichment.objects.filter(id=request.id).update)(
                completion_percentage=percentage
            )
            
            # Update status metadata with detailed progress
            status_metadata = {
                "total_partitions": total_partitions,
                "processed_partitions": processed_partitions,
                "failed_partitions": failed_partitions,
                "pending_partitions": total_partitions - total_processed,
                "completion_percentage": percentage,
                "last_updated": timezone.now().isoformat(),
                "company_id": str(request.company.id)
            }
            await sync_to_async(DataEnrichment.objects.filter(id=request.id).update)(
                status_metadata=status_metadata
            )
            
            print(f"\n📊 Progress Update: {percentage}% complete ({total_processed}/{total_partitions} partitions)")
            print(f"   ✅ Successful: {processed_partitions}")
            print(f"   ❌ Failed: {failed_partitions}")
            print(f"   ⏳ Pending: {total_partitions - total_processed}")
            
        except Exception as e:
            print(f"\n⚠️ Error updating completion percentage: {str(e)}")
            logger.add(f"Error updating completion percentage: {str(e)}")

    def _get_enricher(self, request: DataEnrichment) -> BaseDataEnricher:
        """Get the appropriate enricher based on the model name"""
        enricher = BaseDataEnricher.get_enricher(request.llm_model)
        
        # Initialize enricher with company and session info
        enricher.setup(company=request.company, session_id=str(request.session_id), request_name=request.name)
        
        return enricher

    def enrich_data(self, request: DataEnrichment) -> None:
        """Enrich data for a request"""
        try:
            print(f"\n🔄 Starting data enrichment for request {request.id}")
            
            # Read input file
            input_path = os.path.join(settings.MEDIA_ROOT, request.input_file.path)
            print(f"   Input file path: {input_path}")
            df = self._read_input_file(input_path)
            print(f" Read {len(df)} records from input file")
            CompanyUtils.set_company_registry(request.company)
            if request.status == DataEnrichment.STATUS_PENDING:
                # Create partitions
                partitions = self.create_partition_files(request, df)
                print(f"   Created {len(partitions)} partitions")
                request.status = DataEnrichment.STATUS_PARTITION_CREATED
                request.save()
            else:
                partitions = DataEnrichmentPartition.objects.filter(request=request, status=DataEnrichmentPartition.STATUS_PENDING)
            print(f"   Found {len(partitions)} partitions to process")
            request.status = DataEnrichment.STATUS_PROCESSING
            request.execution_start_at=timezone.now()
            request.save()
            # Process partitions in parallel
            prompt_template = self._get_prompt_template(request)
            # print(f"   Prompt template: {prompt_template}")
            asyncio.run(self._process_partitions(
                request=request,
                partitions=partitions,
                prompt_template=prompt_template
            ))
            
            # Combine output files
            if request.combine_output_files:
                self._combine_output_files(request)
            
            # Update request status
            request.status = DataEnrichment.STATUS_DONE
            request.processed_at = timezone.now()
            request.save()
            
            print(f"✅ Successfully completed data enrichment for request {request.id}")
            
        except Exception as e:
            error_msg = f"Error enriching data: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            
            # Update request status
            request.status = DataEnrichment.STATUS_ERROR
            request.error_message = str(e)
            request.save()
            raise

    async def _process_partitions(self, request: DataEnrichment, partitions: List[DataEnrichmentPartition], prompt_template: str) -> None:
        """Process partitions in parallel"""
        try:
            # Process partitions in parallel batches
            total_partitions = len(partitions)
            processed = 0
            PARALLEL_EXECUTION_COUNT = request.parallel_threading_count if request.parallel_threading_count else PARALLEL_EXECUTION_COUNT
            print("\n" + "="*60)
            print("🚀 STARTING PARALLEL PROCESSING")
            print(f"   Total Partitions: {total_partitions}")
            print(f"   Parallel Count: {PARALLEL_EXECUTION_COUNT}")
            print("="*60 + "\n")
            while processed < total_partitions:
                batch = partitions[processed:processed + PARALLEL_EXECUTION_COUNT]
                tasks = []
                
                # Create tasks for batch
                for partition in batch:
                    print(f"\n📦 Processing Partition {partition.id}")
                    print(f"   Status: {partition.status}")
                    print(f"   Input: {partition.input_file_path}")
                    
                    task = asyncio.create_task(
                        self._process_partition(
                            partition=partition,
                            request=request,
                            prompt_template=prompt_template
                        )
                    )
                    tasks.append(task)
                
                # Wait for batch to complete
                try:
                    await asyncio.gather(*tasks)
                except Exception as e:
                    print(f"\n⚠️ Error in batch: {str(e)}")
                    logger.add(f"Error in batch: {str(e)}")
                
                # Update progress
                processed += len(batch)
                await self._update_completion_percentage(request)
            
            print(f"\n✅ Successfully processed all {total_partitions} partitions")
            
        except Exception as e:
            error_msg = f"Error processing partitions: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            raise

    async def _process_partition(self, partition: DataEnrichmentPartition, request: DataEnrichment, prompt_template: str) -> None:
        """Process a single partition"""
        try:
            print("\n" + "="*60)
            print(f"📦 PROCESSING PARTITION {partition.id}")
            print(f"   Status: {partition.status}")
            print("="*60)
            
            #asyncio.sleep(10);
            #return;

            # Update partition status to processing
            await sync_to_async(DataEnrichmentPartition.objects.filter(id=partition.id).update)(
                status=DataEnrichmentPartition.STATUS_PROCESSING,
                processed_at=timezone.now()
            )
            
            # Read partition data
            input_path = os.path.join(settings.MEDIA_ROOT, partition.input_file_path)
            output_path = os.path.join(settings.MEDIA_ROOT, partition.output_file_path)
            
            print("\n📂 File Paths:")
            print(f"   Input: {input_path}")
            print(f"   Output: {output_path}")
            
            with open(input_path, 'r') as f:
                partition_data = json.load(f)
            
            print("\n📊 Partition Data:")
            print(f"   Records: {len(partition_data.get('data', []))}")
            print(f"   Metadata: {json.dumps(partition_data.get('metadata', {}), indent=2)}")
            
            # Process the partition data
            print("\n🔄 Processing Data...")
            df = pd.DataFrame(partition_data.get("data", []))
            enriched_data = await sync_to_async(self._process_batch, thread_sensitive=False)(
                batch=df,
                prompt_template=prompt_template,
                request=request
            )
            
            try:
                # Parse enriched data and validate
                enriched_json = json.loads(enriched_data)
                if not isinstance(enriched_json, list):
                    enriched_json = [enriched_json]
                    
                # Validate record count
                if len(enriched_json) != len(df):
                    print(f"\n⚠️ Warning: Response count ({len(enriched_json)}) doesn't match input ({len(df)})")
                    
                    # If we got fewer records than input, pad with error records
                    if len(enriched_json) < len(df):
                        print("   Padding missing records with errors")
                        while len(enriched_json) < len(df):
                            enriched_json.append({
                                "error": "Record missing from LLM response",
                                "error_type": "missing_record",
                                "timestamp": datetime.now().isoformat()
                            })
                    # If we got more records than input, truncate
                    elif len(enriched_json) > len(df):
                        print("   Truncating extra records")
                        enriched_json = enriched_json[:len(df)]
                
            except json.JSONDecodeError as e:
                print(f"\n❌ Invalid JSON response: {str(e)}")
                print("   Using error records")
                enriched_json = [
                    {
                        "error": "Invalid JSON response from LLM",
                        "error_type": "invalid_json",
                        "raw_response": enriched_data[:200] + "..." if len(enriched_data) > 200 else enriched_data,
                        "timestamp": datetime.now().isoformat()
                    }
                ] * len(df)
            
            # Preserve input structure in output
            output_data = {
                "data": enriched_json,
                "metadata": {
                    **partition_data.get("metadata", {}),
                    "total_records": len(partition_data.get("data", [])),
                    "successful_records": sum(1 for r in enriched_json if "error" not in r),
                    "failed_records": sum(1 for r in enriched_json if "error" in r),
                    "model": request.llm_model,
                    "timestamp": datetime.now().isoformat(),
                    "partition_id": str(partition.id)
                }
            }
            
            # Save enriched data
            print("\n💾 Saving Results...")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            # Update partition metadata
            metadata = output_data["metadata"]
            
            print("\n📊 Processing Summary:")
            print(f"   Total Records: {metadata['total_records']}")
            print(f"   Successful: {metadata['successful_records']}")
            print(f"   Failed: {metadata['failed_records']}")
            print(f"   Model: {metadata['model']}")
            
            # Update partition status
            await sync_to_async(DataEnrichmentPartition.objects.filter(id=partition.id).update)(
                status=DataEnrichmentPartition.STATUS_DONE,
                metadata=metadata
            )
            
            # Update completion percentage
            await self._update_completion_percentage(request)
            
            # Create ingestion entry for the enriched partition
            ingestion, ingestion_partition = await sync_to_async(self.create_ingestion_for_enriched_data)(request, partition)
            if not ingestion or not ingestion_partition:
                logger.warning(f"Failed to create ingestion for enriched partition {partition.id}")
            else:
                print(f"\n✅ Successfully created ingestion entry {ingestion.id} with partition {ingestion_partition.id}")
            
            print("\n✅ PARTITION PROCESSING COMPLETED")
            print("="*60 + "\n")
            
        except Exception as e:
            error_msg = f"Error processing partition {partition.id}: {str(e)}"
            print("\n❌ PARTITION PROCESSING FAILED")
            print(f"   Error: {str(e)}")
            print("="*60 + "\n")
            logger.add(error_msg)
            
            # Update partition status
            await sync_to_async(DataEnrichmentPartition.objects.filter(id=partition.id).update)(
                status=DataEnrichmentPartition.STATUS_ERROR,
                error_message=str(e)
            )
            
            # Update completion percentage after error
            await self._update_completion_percentage(request)
            
            raise

    def create_ingestion_for_enriched_data(self, enrichment_request: DataEnrichment, partition: DataEnrichmentPartition):
        """
        Create a data ingestion entry for an enriched partition file.
        This function is called after a partition has been successfully enriched.
        
        Args:
            enrichment_request: The DataEnrichment request
            partition: The DataEnrichmentPartition that was enriched
            
        Returns:
            tuple: (ingestion_request, ingestion_partition) or (None, None) if error
        """
        try:
            CompanyUtils.set_company_registry(enrichment_request.company)
            print("\n🔄 Creating ingestion entry for enriched data")
            print(f"   Enrichment Request: {enrichment_request.id}")
            print(f"   Partition: {partition.id}")
            
            # Check if ingestion already exists for this session
            ingestion = DataIngestion.objects.filter(
                session_id=enrichment_request.session_id,
                company=enrichment_request.company
            ).first()
            
            if not ingestion:
                # Create new ingestion request with detailed status metadata
                status_metadata = {
                    "source": "data_enrichment",
                    "enrichment_id": str(enrichment_request.id),
                    "enrichment_name": enrichment_request.name,
                    "enrichment_model": enrichment_request.llm_model,
                    "enrichment_prompt": enrichment_request.prompt,
                    "enrichment_batch_size": enrichment_request.batch_size,
                    "created_at": timezone.now().isoformat(),
                    "total_partitions": enrichment_request.get_total_partitions_count(),
                    "processed_partitions": enrichment_request.get_processed_partitions_count(),
                    "failed_partitions": enrichment_request.get_failed_partitions_count(),
                    "completion_percentage": enrichment_request.completion_percentage,
                    "company_id": str(enrichment_request.company.id)
                }
                
                ingestion = DataIngestion.objects.create(
                    name=f"Auto Ingestion - {enrichment_request.name}",
                    company=enrichment_request.company,
                    session_id=enrichment_request.session_id,
                    execution_type=DataIngestion.EXECUTION_TYPE_PROMPT,
                    schema_type=DataIngestion.SCHEMA_TYPE_DEFINED,
                    prompt_name='ingest_enriched_data',
                    prompt_defined_schema='ingest_enriched_schema',
                    chunk_size=enrichment_request.batch_size,
                    chunk_overlap=0,
                    status=DataIngestion.STATUS_INITIATED,
                    status_metadata=json.dumps(status_metadata)
                )
                print(f"✅ Created new ingestion request: {ingestion.id}")
            
            # Create ingestion partition with detailed metadata
            partition_metadata = {
                'source_enrichment_partition': str(partition.id),
                'source_enrichment_request': str(enrichment_request.id),
                'created_at': timezone.now().isoformat(),
                'partition_index': partition.metadata.get('partition_index'),
                'total_partitions': partition.metadata.get('total_partitions'),
                'record_count': partition.metadata.get('record_count'),
                'company_id': str(enrichment_request.company.id)
            }
            
            ingestion_partition, created = DataIngestionPartition.objects.get_or_create(
                request=ingestion,
                input_file_path=partition.output_file_path,
                defaults={
                    'status': DataIngestionPartition.STATUS_PENDING,
                    'company': enrichment_request.company,
                    'metadata': partition_metadata
                }
            )
            
            if created:
                print(f"✅ Created new ingestion partition: {ingestion_partition.id}")
            else:
                print(f"ℹ️ Using existing ingestion partition: {ingestion_partition.id}")
            
            return ingestion, ingestion_partition
            
        except Exception as e:
            error_msg = f"Error creating ingestion for enriched data: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            return None, None

    def create_partition_files(self, request: DataEnrichment, df: pd.DataFrame) -> List[DataEnrichmentPartition]:
        """Create partition files for parallel processing"""
        try:
            print("\n📦 Creating partition files")
            print(f"\n - Batch size: {request.batch_size}")
            # Calculate partition size and count
            total_records = len(df)
            partition_size = request.batch_size
            partition_count = math.ceil(total_records / partition_size)
            
            print(f"   Total records: {total_records}")
            print(f"   Partition size: {partition_size}")
            print(f"   Number of partitions: {partition_count}")
            
            # Create partitions
            partitions = []
            for i in range(partition_count):
                start_idx = i * partition_size
                end_idx = min((i + 1) * partition_size, total_records)
                
                # Create partition data
                partition_data = {
                    "data": df.iloc[start_idx:end_idx].to_dict(orient='records'),
                    "metadata": {
                        "partition_index": i,
                        "total_partitions": partition_count,
                        "start_index": start_idx,
                        "end_index": end_idx,
                        "record_count": end_idx - start_idx,
                        "company_id": str(request.company.id),
                        "request_id": str(request.id)
                    }
                }
                
                # Generate unique partition paths
                partition_dir = os.path.join(
                    settings.MEDIA_ROOT,
                    'data_enrichment',
                    str(request.company.id),
                    str(request.id),
                    'partitions',
                    str(i)
                )
                os.makedirs(partition_dir, exist_ok=True)
                
                input_file = os.path.join(partition_dir, 'input.json')
                output_file = os.path.join(partition_dir, 'output.json')
                
                # Save partition data
                with open(input_file, 'w') as f:
                    json.dump(partition_data, f, indent=2)
                # Create partition record
                CompanyUtils.set_company_registry(request.company)
                print(" - Partition Saving Process Started")
                partition = DataEnrichmentPartition.objects.create(
                    request=request,
                    input_file_path=os.path.relpath(input_file, settings.MEDIA_ROOT),
                    output_file_path=os.path.relpath(output_file, settings.MEDIA_ROOT),
                    status=DataEnrichmentPartition.STATUS_PENDING,
                    metadata={
                        "partition_index": i,
                        "total_partitions": partition_count,
                        "record_count": end_idx - start_idx,
                        "company_id": str(request.company.id),
                        "request_id": str(request.id),
                        "timestamp": timezone.now().isoformat()
                    }
                )
                print(" - Partition Saving Process Completed")
                partitions.append(partition)
            print(f"✅ Successfully created {len(partitions)} partition files")
            return partitions
            
        except Exception as e:
            error_msg = f"Error creating partition files: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            raise

    def _combine_output_files(self, request: DataEnrichment) -> None:
        """Combine all processed partition files into a single output file"""
        try:
            print("\n🔄 Combining output files")
            
            # Check if all partitions are processed
            total_partitions = request.get_total_partitions_count()
            processed_partitions = request.get_processed_partitions_count()
            failed_partitions = request.get_failed_partitions_count()
            pending_partitions = total_partitions - processed_partitions - failed_partitions
            
            print(f"   - Total partitions: {total_partitions}")
            print(f"   - Processed: {processed_partitions}")
            print(f"   - Failed: {failed_partitions}")
            print(f"   - Pending: {pending_partitions}")
            
            if pending_partitions > 0:
                error_msg = f"Cannot combine files: {pending_partitions} partitions still pending"
                print(f"\n❌ {error_msg}")
                logger.add(error_msg)
                raise ValueError(error_msg)
            
            if processed_partitions == 0:
                error_msg = "No partitions were successfully processed"
                print(f"\n❌ {error_msg}")
                logger.add(error_msg)
                raise ValueError(error_msg)
            
            # Get all successfully processed partitions
            processed_partitions = request.partitions.filter(
                status=DataEnrichmentPartition.STATUS_DONE
            ).order_by('created_at')
            
            # Initialize counters
            total_records = 0
            successful_records = 0
            failed_records = 0
            all_data = []
            
            # Read original input file to get structure
            input_file_path = os.path.join(settings.MEDIA_ROOT, request.input_file.name)
            with open(input_file_path, 'r') as f:
                input_data = json.load(f)
            input_structure = "list" if isinstance(input_data, list) else "dict"
            
            # Combine data from all processed partitions
            for partition in processed_partitions:
                output_path = os.path.join(settings.MEDIA_ROOT, partition.output_file_path)
                
                try:
                    with open(output_path, 'r') as f:
                        partition_data = json.load(f)
                        
                    # Extract records and update counters
                    records = partition_data.get('data', [])
                    total_records += len(records)
                    successful_records += sum(1 for r in records if "error" not in r)
                    failed_records += sum(1 for r in records if "error" in r)
                    all_data.extend(records)
                    
                except Exception as e:
                    error_msg = f"Error reading partition file {partition.id}: {str(e)}"
                    print(f"\n❌ {error_msg}")
                    logger.add(error_msg)
                    continue
            
            if not all_data:
                error_msg = "No data found in processed partitions"
                print(f"\n❌ {error_msg}")
                logger.add(error_msg)
                raise ValueError(error_msg)
            
            # Prepare output directory
            output_dir = os.path.join(
                settings.MEDIA_ROOT,
                'data_enrichment',
                'outputs',
                str(request.company.id),
                timezone.now().strftime('%Y/%m/%d'),
                str(request.id)
            )
            os.makedirs(output_dir, exist_ok=True)
            
            # Save combined output file
            output_filename = f'enriched_data_{request.id}.json'
            output_path = os.path.join(output_dir, output_filename)
            
            # Match input file structure
            if input_structure == "list":
                output_data = all_data
            else:
                output_data = {
                    "data": all_data,
                    "metadata": {
                        "request_id": str(request.id),
                        "company_id": str(request.company.id),
                        "session_id": request.session_id,
                        "total_records": total_records,
                        "successful_records": successful_records,
                        "failed_records": failed_records,
                        "total_partitions": total_partitions,
                        "processed_partitions": len(processed_partitions),
                        "failed_partitions": failed_partitions,
                        "processed_at": timezone.now().isoformat(),
                        **input_data.get("metadata", {})  # Preserve original metadata
                    }
                }
            
            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)
                
            # Update request with output file path
            request.output_file = os.path.relpath(output_path, settings.MEDIA_ROOT)
            request.status = DataEnrichment.STATUS_DONE
            request.execution_end_at = timezone.now()
            request.save()
            
            logger.add(f"Successfully combined {len(processed_partitions)} partitions with {len(all_data)} total records")
            print(f"\n✅ Successfully combined {len(processed_partitions)} partitions")
            print(f"   - Total records: {total_records}")
            print(f"   - Successful: {successful_records}")
            print(f"   - Failed: {failed_records}")
            print(f"   - Output format: {input_structure}")
            
        except Exception as e:
            error_msg = f"Error combining output files: {str(e)}"
            logger.add(error_msg)
            print(f"\n❌ {error_msg}")
            raise ValueError(error_msg)

    def _get_prompt_template(self, request: DataEnrichment) -> str:
        """Fetch and validate prompt template from Langfuse"""
        try:
            print("\n🔄 Fetching prompt template")
            print(f"   Prompt name: {request.prompt}")
            
            # Initialize Langfuse service with company context
            if not self.langfuse_service:
                self.langfuse_service = LangfuseService(
                    company_id=request.company.id,
                    session_id=request.session_id
                )
                print(f"✅ Initialized Langfuse service for company {request.company.id}")
            
            # Get prompt config
            prompt_config = self.langfuse_service.get_prompt(request.prompt)
            if not prompt_config:
                raise ValueError(f"Prompt '{request.prompt}' not found in Langfuse")
                
            # Extract prompt template
            if isinstance(prompt_config, dict):
                prompt_template = prompt_config.get('prompt', '')
            else:
                prompt_template = getattr(prompt_config, 'prompt', '')
                
            if not prompt_template:
                raise ValueError(f"Invalid prompt template for '{request.prompt}'")
                
            print(f"✅ Successfully fetched prompt template")
            # print(f"   Template: {prompt_template}")
            
            return prompt_template
            
        except Exception as e:
            error_msg = f"Error fetching prompt template: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            raise

    def _handle_error(self, request: DataEnrichment, error: Exception) -> None:
        """Handle errors during processing"""
        try:
            error_msg = str(error)
            print(f"\n❌ Error processing request {request.id}: {error_msg}")
            logger.add(error_msg)
            
            # Update request status
            request.status = DataEnrichment.STATUS_ERROR
            request.error_message = error_msg
            request.execution_end_at = timezone.now()
            request.save()
            
            # Update status metadata
            request.status_metadata = {
                "error": error_msg,
                "error_type": "request_processing_error",
                "timestamp": timezone.now().isoformat(),
                "company_id": str(request.company.id),
                "request_id": str(request.id),
                "session_id": request.session_id
            }
            request.save()
            
            # Create error response file
            error_filename = f'error_{request.id}.json'
            error_dir = os.path.join(
                settings.MEDIA_ROOT,
                'data_enrichment',
                'errors',
                str(request.company.id),
                datetime.now().strftime('%Y/%m/%d/%H'),
                str(request.id)
            )
            os.makedirs(error_dir, exist_ok=True)
            
            # Save error details
            error_path = os.path.join(error_dir, error_filename)
            error_data = {
                "error": error_msg,
                "error_type": "request_processing_error",
                "timestamp": timezone.now().isoformat(),
                "metadata": {
                    "company_id": str(request.company.id),
                    "request_id": str(request.id),
                    "session_id": request.session_id,
                    "model": request.llm_model,
                    "input_file": request.input_file_path if request.input_file else None,
                    "output_file": request.output_file_path if request.output_file else None,
                    "status": request.status,
                    "execution_start": request.execution_start_at.isoformat() if request.execution_start_at else None,
                    "execution_end": request.execution_end_at.isoformat() if request.execution_end_at else None
                },
                "traceback": ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            }
            
            with open(error_path, 'w') as f:
                json.dump(error_data, f, indent=2)
            
            # Update request with error file path
            request.error_file = os.path.relpath(error_path, settings.MEDIA_ROOT)
            request.save()
            
            print(f"✅ Error details saved to: {error_path}")
            
        except Exception as e:
            error_msg = f"Error handling error: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            raise

    def _process_batch(self, batch: pd.DataFrame, prompt_template: str, request: DataEnrichment) -> str:
        """Process a batch of data using the selected enricher in a single LLM call"""
        try:
            print("\n" + "="*60)
            print("🔄 BATCH PROCESSING STARTED")
            print(f"   Records in batch: {len(batch)}")
            print("="*60)
            
            # Get enricher
            enricher = self._get_enricher(request)
            
            # Convert batch to list of dictionaries
            batch_data = batch.to_dict(orient='records')
            print("\n📋 Batch Data Structure:")
            print(f"   Type: {type(batch_data)}")
            print(f"   Length: {len(batch_data)}")
            if batch_data:
                print(f"   Sample Keys: {list(batch_data[0].keys())}")
            
            # Process batch
            # print("Printing batch_data", batch_data)
            print("\n🔄 Printing Enricher", enricher)
            result = enricher.process_data({
                "data": batch_data,
                "prompt_template": prompt_template,
                "metadata": {
                    "request_id": str(request.id),
                    "company_id": str(request.company.id),
                    "batch_size": len(batch_data)
                }
            })
            
            # Validate response format
            if "error" in result:
                print("\n❌ Batch Processing Error:")
                print(f"   Error: {result['error']}")
                print(f"   Type: {result.get('error_type', 'unknown')}")
                raise ValueError(result["error"])
            
            # Extract response from Vertex AI format
            response_text = result.get("response", "")
            if not response_text:
                error_msg = "Empty response from enricher"
                print(f"\n❌ {error_msg}")
                raise ValueError(error_msg)
            
            # Parse response
            try:
                # Clean and parse the response text
                print("\n Printing | Cleaning and parsing response...", response_text)
                enriched_data = self.clean_and_parse_json(response_text)
                parsed_data = json.loads(enriched_data)
                
                # Validate we got back the same number of records
                if isinstance(parsed_data, list):
                    if len(parsed_data) != len(batch_data):
                        print(f"\n⚠️ Warning: Response record count ({len(parsed_data)}) doesn't match input ({len(batch_data)})")
                
                print("\n✅ Response Validation:")
                print(f"   Records: {len(parsed_data)}")
                print(f"   Size: {len(enriched_data)} bytes")
                
                # Return the cleaned and validated JSON string
                return json.dumps(parsed_data, ensure_ascii=False)
                
            except Exception as e:
                print("\n❌ Response Parsing Error:")
                print(f"   Error: {str(e)}")
                print(f"   Raw Response: {response_text[:200]}...")
                raise
            
            # Log metadata for debugging
            if result.get("metadata"):
                print("\n📊 Response Metadata:")
                print(f"   Model: {result['metadata'].get('model')}")
                print(f"   Timestamp: {result['metadata'].get('timestamp')}")
                print(f"   Config: {result['metadata'].get('generation_config')}")
            
            print("="*60)
            print("✅ BATCH PROCESSING COMPLETED")
            print("="*60 + "\n")
            
        except Exception as e:
            error_msg = f"Batch processing failed: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            raise

    def clean_and_parse_json(self, json_str):
        """Clean and parse JSON string with proper error handling"""
        if not json_str:
            raise ValueError("Empty JSON string provided")
            
        try:
            print(f"\n🔍 Attempting direct JSON parsing...")
            # First try direct parsing
            data = json.loads(json_str, strict=False)
            if isinstance(data, list):
                print(f"✅ Direct parsing successful - Found {len(data)} records")
            else:
                print(f"✅ Direct parsing successful - Found single object")
            return json.dumps(data, ensure_ascii=False)
            
        except json.JSONDecodeError as e:
            try:
                print(f"\n🧹 Cleaning JSON string...")
                
                # Remove markdown and clean string
                json_str = json_str.strip()
                json_str = json_str.replace('```json', '').replace('```', '')
                json_str = json_str.replace('None', 'null')
                json_str = json_str.replace('True', 'true')
                json_str = json_str.replace('False', 'false')
                
                # Try to find array first
                if '[' in json_str and ']' in json_str:
                    try:
                        # Find the outermost array
                        depth = 0
                        start = -1
                        for i, char in enumerate(json_str):
                            if char == '[':
                                if depth == 0:
                                    start = i
                                depth += 1
                            elif char == ']':
                                depth -= 1
                                if depth == 0 and start != -1:
                                    array_str = json_str[start:i+1].strip()
                                    data = json.loads(array_str)
                                    if isinstance(data, list):
                                        print(f"✅ Found array with {len(data)} items")
                                        return json.dumps(data, ensure_ascii=False)
                    except:
                        print("   Array parsing failed, trying object parsing...")
                
                # Extract all JSON objects
                objects = []
                depth = 0
                start = -1
                in_string = False
                escape = False
                
                print("   Scanning for JSON objects...")
                for i, char in enumerate(json_str):
                    # Handle string literals
                    if char == '"' and not escape:
                        in_string = not in_string
                    elif char == '\\' and not escape:
                        escape = True
                        continue
                    
                    if not in_string:
                        if char == '{':
                            if depth == 0:
                                start = i
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0 and start != -1:
                                obj_str = json_str[start:i+1].strip()
                                try:
                                    # Validate each object
                                    obj = json.loads(obj_str)
                                    objects.append(obj)
                                    print(f"   Found valid JSON object ({len(obj_str)} chars)")
                                except:
                                    print(f"   Skipping invalid JSON object")
                                start = -1
                    
                    escape = False
                
                if not objects:
                    print("\n❌ No valid JSON objects found")
                    print(f"Raw string preview: {json_str[:200]}...")
                    raise ValueError("No valid JSON objects found")
                
                print(f"   Found {len(objects)} valid JSON objects")
                
                # Return array of objects
                return json.dumps(objects, ensure_ascii=False)
                
            except Exception as inner_e:
                print("\n❌ JSON cleaning failed:")
                print(f"   Error: {str(inner_e)}")
                print(f"   Raw string preview: {json_str[:200]}...")
                raise ValueError(f"Failed to parse JSON: {str(inner_e)}")

    def _read_input_file(self, file_path: str) -> pd.DataFrame:
        """Read input file in various formats (CSV, XLSX, JSON) into a pandas DataFrame
        
        Args:
            file_path: Path to the input file
            
        Returns:
            pandas.DataFrame: DataFrame containing the input data
        """
        try:
            print(f"\n📖 Reading input file: {file_path}")
            
            # Determine file format from extension
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # Try different encodings
                encodings = ['utf-8', 'latin1', 'cp1252']
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        print(f"✅ Successfully read CSV file with {encoding} encoding")
                        return df
                    except UnicodeDecodeError:
                        continue
                raise ValueError(f"Could not read CSV file with any of the encodings: {encodings}")
                
            elif file_ext == '.xlsx':
                df = pd.read_excel(file_path)
                print("✅ Successfully read Excel file")
                return df
                
            elif file_ext == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                # Handle different JSON structures
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    if 'data' in data and isinstance(data['data'], list):
                        df = pd.DataFrame(data['data'])
                    else:
                        df = pd.DataFrame([data])
                else:
                    raise ValueError("Invalid JSON structure")
                    
                print("✅ Successfully read JSON file")
                return df
                
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
            
        except Exception as e:
            error_msg = f"Error reading input file: {str(e)}"
            print(f"\n❌ {error_msg}")
            logger.add(error_msg)
            raise
