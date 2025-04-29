from typing import List, Dict, Any, Optional
from langfuse import Langfuse
from basics.custom_exception import (
    CompanyNotFoundException,
    LangfuseConnectionException,
    PromptNotFoundException
)
from company.models import Company
from company.utils import CompanyUtils
from chat.constants import CURRENT_ENVIRONMENT
from requests.auth import HTTPBasicAuth
import requests
from decouple import config

from backend.logger import Logger

logger = Logger(Logger.INFO_LOG)


class LangfuseService:
    """Service class for Langfuse prompt management"""
    
    def __init__(self, company_id: Optional[int] = None, session_id: Optional[str] = None):
        """
        Initialize Langfuse service for a specific company.
        If company_id not provided, fetches current company from registry.
        """
        self.langfuse_host = config('LANGFUSE_HOST', default=None)
        self.get_all_prompts_api_url =f"{self.langfuse_host}/api/public/v2/prompts"     
        try:
            if company_id is not None:
                self.company = CompanyUtils.get_company_from_company_id(company_id)
                self.company_id = company_id
            else:
                self.company = CompanyUtils.get_current_company_object()
                self.company_id = self.company.id if self.company else None
            if not self.company:
                logger.add(f"Company not found, for company_id: {self.company_id}")    
                raise CompanyNotFoundException(f"Company with {self.company_id} not found")
            
            # Set company in registry for downstream services
            CompanyUtils.set_company_registry(self.company)
            
            if not self.langfuse_host:
                logger.add("LANGFUSE_HOST environment variable not set")
                raise ValueError("LANGFUSE_HOST environment variable not set")
                
            self.client = Langfuse(
                public_key=self.company.langfuse_public_key, 
                secret_key=self.company.langfuse_secret_key,
                host=self.langfuse_host
            )
            logger.add(f"Successfully initialized Langfuse client for company {self.company_id}")
        except CompanyNotFoundException:
            raise
        except Exception as e:
            logger.add(f"Failed to initialize Langfuse client for company {self.company_id}: {str(e)}")
            raise LangfuseConnectionException(f"Langfuse connection error in company {self.company_id}: {e}")

    def get_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """Get a specific prompt configuration from Langfuse"""
        try:
            # Try labeled prompt first
            prompt_langfuse = self.client.get_prompt(
                prompt_name, 
                cache_ttl_seconds=86400, 
                label=CURRENT_ENVIRONMENT
            )
            logger.add(f"Retrieved labeled prompt {prompt_name} for company {self.company_id}")
            return prompt_langfuse
        except Exception:
            try:
                # Fallback to default prompt
                prompt_langfuse = self.client.get_prompt(
                    prompt_name, 
                    cache_ttl_seconds=86400
                )
                logger.add(f"Retrieved default prompt {prompt_name} for company {self.company_id}")
                return prompt_langfuse
            except Exception as default_exception:
                logger.add(f"Failed to retrieve prompt {prompt_name} for company {self.company_id}: {str(default_exception)}")
                raise PromptNotFoundException(
                    f"company {self.company_id} | Error: Langfuse - {default_exception}"
                )

    def get_all_prompts(self) -> List[str]:
        """Get all available prompt names from Langfuse"""
        available_prompts = set()
        
        try:
            available_prompts = self.get_prompts(
                label=CURRENT_ENVIRONMENT,
                cache_ttl_seconds=86400
            )
            
            print(available_prompts)
            print(CURRENT_ENVIRONMENT)
            logger.add(f"Retrieved {len(available_prompts)} labeled prompts for company {self.company_id}")
        except Exception as e:
            logger.add(f"Failed to fetch prompts from {CURRENT_ENVIRONMENT} environment: {str(e)}")
            print(f"Failed to fetch prompts from {CURRENT_ENVIRONMENT} environment: {str(e)}")
        
        if not available_prompts:
            logger.add(f"No prompts found for company {self.company_id}")
            
        return list(available_prompts)

    def get_prompts(self, label, cache_ttl_seconds):
        # Use HTTPBasicAuth to handle Basic Authentication
        auth = HTTPBasicAuth(self.company.langfuse_public_key, self.company.langfuse_secret_key)
        try:
            available_prompts = set()
            params={
                    "label": label,
                    "cache_ttl_seconds": cache_ttl_seconds
                }
            response = requests.get(self.get_all_prompts_api_url, auth=auth, params=params)
            response.raise_for_status()  # Raise error for HTTP 4xx/5xx
            response_data =response.json()
            if response_data and 'data' in response_data:
                for prompt in response_data['data']:
                    if 'name' in prompt:
                        prompt_name = prompt['name']
                        available_prompts.add(prompt_name)
            return available_prompts
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch prompts: {e}")
            return None

    @classmethod
    def create(cls, company_id: Optional[int] = None) -> 'LangfuseService':
        """
        Factory method to create a LangfuseService instance.
        If company_id not provided, fetches current company from registry.
        """
        return cls(company_id=company_id)