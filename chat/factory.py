import json
import os
import re
import sys
from typing import Dict

from backend import settings

sys.path.append('..')
import importlib


def get_client_class(company_name):
    try:
        company_name = re.sub(r'[^a-zA-Z0-9]', '', company_name)
        module = importlib.import_module(f"chat.clients.{company_name.lower()}")
        print(module, company_name.capitalize())
        return getattr(module, company_name.capitalize())()
    except (ModuleNotFoundError, AttributeError):
        raise ValueError(f"No class defined for the organization: {company_name.capitalize()}")

def get_client_workflow(company_name):
    try:
        company_name = re.sub(r'[^a-zA-Z0-9]', '', company_name)
        module = importlib.import_module(f"chat.clients.workflows.{company_name.lower()}")
        return module
    except (ModuleNotFoundError, AttributeError):
        raise ValueError(f"No class defined for the organization: {company_name.capitalize()}")

# Usage example
def get_specific_workflow(company_name: str, workflow_name: str):
    company_name = re.sub(r'[^a-zA-Z0-9]', '', company_name)
    company_module = get_client_workflow(company_name)
    try:
        workflow_module = importlib.import_module(f"{company_module.__name__}.{workflow_name}")
        return workflow_module
    except (ModuleNotFoundError, AttributeError) as e:
        raise ValueError(f"Error loading {workflow_name} for company {company_name}: {str(e)}")

def get_llm_class(llm):
    try:
        module = importlib.import_module(f"chat.llms.{llm.lower()}")
        return getattr(module, llm.capitalize())()
    except (ModuleNotFoundError, AttributeError):
        print(AttributeError)
        raise ValueError(f"No class defined for the llm: {llm}")


def get_whatsapp_provider_class(provider, company=None):
    try:
        module = importlib.import_module(f"chat.whatsapp_providers.{provider.lower()}")
        provider_class = getattr(module, provider.capitalize())
        return provider_class(company=company)
    except(ModuleNotFoundError, AttributeError):
        print(AttributeError)
        raise ValueError(f"No class defined for the whatsapp provider: {provider}")
    
def init_whatsapp_provider_class(provider, company=None, api_controller = None):
    """
        Todo : 
        Deprecated : This function is deprecated and will be removed in future release.
    """
    try:
        module = importlib.import_module(f"chat.whatsapp_providers.{provider.lower()}")
        provider_class_name = "".join([part.capitalize() for part in provider.split("_")])
        provider_class = getattr(module, provider_class_name)
        return provider_class(company=company, access_token = api_controller.auth_credentials.get('access_token'), phone_number_id = api_controller.auth_credentials.get('phone_number_id'))
    except(ModuleNotFoundError, AttributeError):
        print(AttributeError)
        raise ValueError(f"No class defined for the whatsapp provider: {provider}")

def get_client_flow_json(company_name: str) -> Dict:
    sanitized_name = ''.join(c.lower() for c in company_name if c.isalnum())
    file_path = os.path.join(settings.BASE_DIR, 'chat', 'clients', 'flows', f"{sanitized_name}.json")
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"No JSON file found for the organization: {company_name}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON file for the organization: {company_name}")