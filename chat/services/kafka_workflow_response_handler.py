from backend.constants import KAFKA_GLOBAL_WAHA_RESPONSE_MESSAGE_QUEUE, KAFKA_GLOBAL_WHATSAPP_RESPONSE_MESSAGE_QUEUE
from backend.services.kafka_service import BaseKafkaService


class KafkaWorkflowResponseHandler:

    def push_wa_message_to_queue(self, wa_message):
        wa_message_json = wa_message.get_wa_json_message()
        BaseKafkaService().push(KAFKA_GLOBAL_WHATSAPP_RESPONSE_MESSAGE_QUEUE, wa_message_json)
        
    def push_waha_message_to_queue(self, waha_message):
        waha_message_json = waha_message.get_waha_json_message()
        BaseKafkaService().push(KAFKA_GLOBAL_WAHA_RESPONSE_MESSAGE_QUEUE, waha_message_json)


class WhatsAppMessageState:

    def __init__(self, phones, message='', template_id='', media='', button_url='', button_type='', content_type='',
                 parameters=None, footer_content='',
                 company=None, whatsapp_provider=None, company_phone_number=None, request_id=None):
        self.phones = phones
        self.message = message
        self.template_id = template_id
        self.media = media
        self.button_url = button_url
        self.button_type = button_type
        self.content_type = content_type
        self.parameters = parameters if parameters is not None else []
        self.footer_content = footer_content
        self.whatsapp_provider = whatsapp_provider
        self.company_phone_number = company_phone_number
        self.company_id = company.id
        self.request_id = request_id

    def get_wa_json_message(self):
        return {
            "mobile_number": self.phones,
            "message": self.message,
            "template_id": self.template_id,
            "media": self.media,
            "button_url": self.button_url,
            "button_type": self.button_type,
            "content_type": self.content_type,
            "parameters": self.parameters if self.parameters is not None else [],
            "footer_content": self.footer_content,
            "whatsapp_provider": self.whatsapp_provider,
            "company_phone_number": self.company_phone_number,
            "company_id": self.company_id,
            "request_id": self.request_id
        }

class WahaMessageState:
    def __init__(self, mobile_number, waha_session, type='', message='', message_id=''):
        self.type = type
        self.mobile_number = mobile_number
        self.message = message
        self.waha_session = waha_session
        self.message_id = message_id
        
        
    def get_waha_json_message(self):
        return {
            "type": self.type,
            "message_id": self.message_id,
            "mobile_number": self.mobile_number,
            "message": self.message,
            "waha_session": self.waha_session
        }