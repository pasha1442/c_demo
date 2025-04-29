from decouple import config

# Defines the maximum number of messages to store in Redis, configurable via the API controller
IN_MEMORY_CHAT_HISTORY_MESSAGE_LIMIT = int(config('IN_MEMORY_CHAT_MESSAGE_LIMIT', default=20))
# Specifies the time (in minutes) after which the chat history will be deleted following the user's last message
IN_MEMORY_CHAT_HISTORY_TIME_LIMIT = config('IN_MEMORY_CHAT_HISTORY_TIME_LIMIT', default=120)
# Specifies the number of messages to be kept in the chat history alongside the generated summary
CHAT_HISTORY_MESSAGES_WITH_SUMMARY_LIMIT = config('CHAT_HISTORY_MESSAGES_WITH_SUMMARY_LIMIT', default=15)
# The maximum number of messages allowed in chat history before generating a summary
SUMMARY_GENERATION_TRIGGER_LIMIT =  config('SUMMARY_GENERATION_TRIGGER_LIMIT', default=40)

CURRENT_ENVIRONMENT = config('CURRENT_ENVIRONMENT')

""" 
WRMQ_EXECUTOR_CONCURRENCY = Whatsapp Request Message Queue 
    - concurrent workers to process "whatsapp_response_message_queue" events
"""

WRMQ_EXECUTOR_CONCURRENCY = int(config('WRMQ_EXECUTOR_CONCURRENCY', 3))

ENABLE_LANGFUSE_TRACING = config('ENABLE_LANGFUSE_TRACING', default=False, cast=bool)

GOOGLE_APPLICATION_CREDENTIALS = config('GOOGLE_APPLICATION_CREDENTIALS', default="")
GCP_CLIENT_DATA_BUCKET_NAME = config('GCP_CLIENT_DATA_BUCKET_NAME', default="")
GCP_PROJECT_ID_FOR_BUCKET = config('GCP_PROJECT_ID_FOR_BUCKET', default="")
GOOGLE_API_KEY = config('GOOGLE_API_KEY', default="")
LOCAL_MODEL_URL = config('LOCAL_MODEL_URL', default="")

STT_LANGUAGE_CODES = {'us_english':'en-US', 'in_english':'en-US', 'hindi': 'hi-IN'}

AI_VOICE_CODES = {'male':{'in_english':'en-IN-Journey-D', 'us_english':'en-US-Journey-D', 'hindi': 'en-IN-Journey-D'}, 'female': {'in_english':'en-IN-Journey-F', 'us_english':'en-US-Journey-F', 'hindi': 'en-IN-Journey-F'}}

TTS_LANGUAGE_CODES = {'us_english':'en-US', 'in_english':'en-IN', 'hindi': 'en-IN'}

CORE_BACKEND_BASE_URL = config('CORE_BACKEND_BASE_URL', default='http://localhost:8000')
DEFAULT_QDRANT_HOST = config('DEFAULT_QDRANT_HOST', default="localhost")
DEFAULT_QDRANT_PORT = config('DEFAULT_QDRANT_PORT', default="6333")

WAHA_SERVER_BASE_URL = config('WAHA_SERVER_BASE_URL', default='http://0.0.0.0:3001')

USE_IMAGE_URL_FOR_ANALYSIS = config('USE_IMAGE_URL_FOR_ANALYSIS', True)