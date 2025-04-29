import os
from typing import Optional
from langchain_core.tools import tool
from chat import factory, utils
from chat.whatsapp_providers.whatsapp_message import WhatsAppMessage
from chat.workflow_utils import get_context
from company.utils import CompanyUtils

@tool
def save_feedback(qna) -> str:
    """
    Saves customer survey feedback to the database

    Args:
        qna : Key, value pairs of feedback questions and their responses
    """
    try:
        context = get_context()
        feedback = qna
        CompanyUtils.set_company_registry(company=context.company)
        utils.save_customer_profile_temp(feedback, context.mobile, context.company)
        extra_save_data = {
            'function_name' : 'save_feedback'
        }
        all_save_data = context.extra_save_data | extra_save_data
        utils.save_conversation(None,'function',context.mobile,"Survey data saved for user",all_save_data)

        return f"Successfully saved data to db: {qna}"
    except Exception as e:

        return f"Failed to execute. Error: {repr(e)}"

@tool
def send_whatsapp_templated_message(template_id: str, query: str, media_url: Optional[str] = None) -> str:
    """
    Sends a templated message through whatsapp.

    Args:
        template_id : template id of the whatsapp template
        query : query to be passed in the template
        media_url (Optional) : media url to be attached to the template_id if provided
    """
    context = get_context()
    CompanyUtils.set_company_registry(company=context.company)
    provider = utils.get_company_whatsapp_provider()
    provider_class = factory.get_whatsapp_provider_class(provider)

    mobile = context.mobile
    extra_save_data = {
        'function_name' : 'send_whatsapp_templated_message'
    }
    all_save_data = context.extra_save_data | extra_save_data
    if(media_url):
        content_type = utils.get_content_type_from_url(media_url=media_url)
            
        wa_message = WhatsAppMessage (
            phones = mobile,
            template_id = template_id,
            media = media_url,
            content_type = content_type
        )
        response = provider_class.send_media_message_with_static_button(wa_message)
        utils.save_conversation(None,'function',context.mobile,f"Succesfully sent template on whatsapp, template_id: {template_id}, query: {query}", all_save_data)
    else:
        wa_message = WhatsAppMessage(
            phones = mobile,
            template_id = template_id
        )
        
        response = provider_class.send_templated_text_message(wa_message)
        utils.save_conversation(None,'function',context.mobile,f"Succesfully sent template on whatsapp, template_id: {template_id}, query: {query}",all_save_data)

    return f"Succesfully sent template on whatsapp, template_id: {template_id}, query: {query}, FINISH your response and wait for the user to answer the question, your response is not required, since the user will read the question through templated message. only respond with FINAL ANSWER"