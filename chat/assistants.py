from basics.custom_exception import CompanyNotFoundException, LangfuseConnectionException, PromptNotFoundException
from chat.constants import CURRENT_ENVIRONMENT
from chat.models import Prompt
from .factory import get_llm_class
from django.core.exceptions import ObjectDoesNotExist
from langfuse import Langfuse
from company.models import Company
from decouple import config


def get_active_prompt(prompt_type, client, chat_history, process_response_method='process_response', version='1.0'):
    try:
        prompt = Prompt.objects.get(prompt_type=prompt_type, active=True, version=version)
        llm_class = get_llm_class(prompt.llm)

        llm_class_response = llm_class.process_request(client, prompt.content, prompt.functions, prompt.model,
                                                       chat_history)
        llm_class_completion = getattr(llm_class, process_response_method)(llm_class_response)

        return llm_class_completion
    except Prompt.DoesNotExist:
        raise ObjectDoesNotExist(f"{prompt_type.replace('_', ' ').title()} not found")


def get_active_master_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('master_assistant', client, chat_history, 'process_master_response', version=version)


def get_active_order_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('order_query_assistant', client, chat_history)


def get_active_brand_support_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('brand_onboarding_assistant', client, chat_history)


def get_active_bulk_order_support_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('bulk_order_assistant', client, chat_history)


def get_active_corp_gifting_support_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('corp_gifting_assistant', client, chat_history)


def get_active_expert_support_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('expert_assistant', client, chat_history, version=version)


def get_active_agent_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('agent_assistant', client, chat_history)


def get_summary_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('summary_assistant', client, chat_history)


def get_further_actions_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('actionables_assistant', client, chat_history)


def get_sentimental_analysis_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('sen_analysis_assistant', client, chat_history)


def get_profile_data_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('profile_data_extracting_assistant', client, chat_history)


def get_agent_evaluation_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('agent_evaluation_prompt', client, chat_history)


def get_survey_prompt(client, chat_history, version='1.0'):
    return get_active_prompt('survey_prompt', client, chat_history)


def get_active_prompt_by_id(id, client, chat_history, process_response_method='process_response', version='1.0'):
    try:
        prompt = Prompt.objects.get(id=id, active=True, version=version)
        llm_class = get_llm_class(prompt.llm)

        llm_class_response = llm_class.process_request(client, prompt.content, prompt.functions, prompt.model,
                                                       chat_history)

        llm_class_completion = getattr(llm_class, process_response_method)(llm_class_response)

        return llm_class_completion
    except Prompt.DoesNotExist:
        raise ObjectDoesNotExist(f"{id.replace('_', ' ').title()} not found")


def get_active_prompt_by_id_for_workflow(id: int, version: str = '1.0') -> dict:
    try:
        prompt = Prompt.objects.get(id=id, active=True, version=version)
        return {
            'llm': prompt.llm,
            'model': prompt.model,
            'functions': prompt.functions,
            'system_prompt': prompt.content
        }
    except Prompt.DoesNotExist:
        raise ObjectDoesNotExist(f"Prompt {id} not found")


def get_active_prompt_from_langfuse(company_id: int, prompt_name: str):
    company = Company.objects.filter(id=company_id).first()
    if company:
        """Adding try catch in case some error occurs in creating new Langfuse instance."""
        try:
            langfuse = Langfuse(public_key=company.langfuse_public_key, secret_key=company.langfuse_secret_key)
        except Exception as e:
            raise LangfuseConnectionException(f"Langfuse connection error in company {company_id}: {e}")
        
        """Adding try catch in case langfuse is unable to get the prompt"""
        try:
            # Attempt to get the labeled prompt
            prompt_langfuse = langfuse.get_prompt(
                prompt_name, 
                cache_ttl_seconds=86400, 
                label=CURRENT_ENVIRONMENT
            )
        except Exception as e:
            # If the labeled prompt is not found, try fetching the default prompt
            try:
                prompt_langfuse = langfuse.get_prompt(
                    prompt_name, 
                    cache_ttl_seconds=86400  # No label for default prompt
                )
            except Exception as default_exception:
                # If the default prompt is also not found, raise a specific exception
                raise PromptNotFoundException(
                    f"company {company_id} | Error: Langfuse - {default_exception}"
                )
        
        prompt_config = prompt_langfuse.config
        
        return {
            'agent': prompt_name,
            'llm': prompt_config["llm"],
            'model': prompt_config["model"],
            'functions': prompt_config["functions"],
            'system_prompt': prompt_langfuse.get_langchain_prompt(),
            'data_source': prompt_config.get("data_source", ""),
            'temperature': prompt_config.get('temperature', None),
            'max_tokens': prompt_config.get('max_tokens', None),
            'ai_voice': prompt_config.get('voice', None),
        }
    else:
        print(f"Error: Company not found, for company_id: {company_id}")    
        raise CompanyNotFoundException(f"Company with {company_id} not found")

