# Variable constants
from django.conf import settings
from decouple import config

CURRENT_USER_ID = "current_user_id"
CURRENT_API_COMPANY = "current_api_company"
API_MOBILE = "mobile_number_in_api_call"

OPENMETER_GLOBAL_OBJ = "openmeter_global_obj"

# Global Kafka Queues
KAFKA_GLOBAL_OPENMETER_QUEUE = "openmeter_events"
KAFKA_GLOBAL_WHATSAPP_REQUEST_MESSAGE_QUEUE = "whatsapp_request_message_queue"
KAFKA_GLOBAL_WHATSAPP_CELERY_REQUEST_MESSAGE_QUEUE = "whatsapp_celery_request_message_queue"
KAFKA_GLOBAL_WHATSAPP_RESPONSE_MESSAGE_QUEUE = "whatsapp_response_message_queue"
KAFKA_GLOBAL_LONG_TERM_MEMORY_GENERATION_QUEUE = "long_term_memory_generation_queue"
KAFKA_GLOBAL_WAHA_REQUEST_MESSAGE_QUEUE = "waha_request_message_queue"
KAFKA_GLOBAL_WAHA_RESPONSE_MESSAGE_QUEUE = "waha_response_message_queue"


API_CONTROLLER_HELP_FILE_PATH = f"{settings.BASE_DIR}/api_controller/help/api_controller_help_content.txt"
DEFAULT_CACHE_KEY_EXPIRY_SECONDS = config('DEFAULT_CACHE_KEY_EXPIRY_SECONDS', default=259200)  # 3 days in seconds