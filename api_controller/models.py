from django.db import models
from chat.models import RequestMedium
from company.models import CompanyBaseModel
from basics.models import BaseModelCompleteUserTimestamps


# time based session Token based session per call per session
class ApiController(CompanyBaseModel, BaseModelCompleteUserTimestamps):
    BaseAPIURL_DEFAULT = "/api/v1/api-controller/invoke-service/"

    BILLING_SESSION_TYPE_PER_CALL_ONE_SESSION = "per_call_one_session"
    BILLING_SESSION_TYPE_TIME_BASED_SESSION = "time_based_session"
    BILLING_SESSION_TYPE_TOKEN_BASED_SESSION = "token_based_session"
    BILLING_SESSION_TYPE_COUNT_AND_TIME_BASED_SESSION = "time_and_count_based_session"

    CONVERSATION_SESSION_TYPE_TIME_BASED_SESSION = "time_based_conversation_session"
    CONVERSATION_SESSION_TYPE_COUNT_BASED_SESSION = "count_based_conversation_session"
    CONVERSATION_SESSION_TYPE_TIME_AND_COUNT_BASED_SESSION = "time_and_count_based_conversation_session"


    APPLICATION_TYPE_BACKEND = 'backend'
    APPLICATION_TYPE_FRONTEND = 'frontend'
    APPLICATION_TYPE_BATCH_PROCESSING = 'batch_processing'
    
    WORKFLOW_TYPE_DEFAULT = 'default'
    WORKFLOW_TYPE_CUSTOM = 'custom'
    
    VOICE_ASSISTANT_METHOD_OPENAI_REALTIME = 'openai_realtime_api'
    VOICE_ASSISTANT_METHOD_WORKFLOW = 'workflow'

    LONG_TERM_MEMORY_VECTOR_STORAGE_NEO4J = 'neo4j'
    LONG_TERM_MEMORY_VECTOR_STORAGE_QDRANT = 'qdrant'


    BaseAPIURL_CHOICES = (
        (BaseAPIURL_DEFAULT, '/api/v1/api-controller/invoke-service/'),
    )

    BILLING_SESSION_TYPE_CHOICES = (
        (BILLING_SESSION_TYPE_PER_CALL_ONE_SESSION, 'Per Call One Session'),
        (BILLING_SESSION_TYPE_TIME_BASED_SESSION, 'Time Based Session'),
        (BILLING_SESSION_TYPE_TOKEN_BASED_SESSION, 'Token Based Session'),
        (BILLING_SESSION_TYPE_COUNT_AND_TIME_BASED_SESSION, 'Count and Time Based Session')
    )

    CONVERSATION_SESSION_TYPE_CHOICES = (
        (CONVERSATION_SESSION_TYPE_TIME_BASED_SESSION, "Time based conversation session"),
        (CONVERSATION_SESSION_TYPE_COUNT_BASED_SESSION, "Count based conversation session"),
        (CONVERSATION_SESSION_TYPE_TIME_AND_COUNT_BASED_SESSION, "Time and Count based conversation session")
    )

    APPLICATION_TYPE_CHOICES = (
        (APPLICATION_TYPE_BACKEND, 'Backend'),
        (APPLICATION_TYPE_FRONTEND, 'Frontend'),
        (APPLICATION_TYPE_BATCH_PROCESSING, 'Batch Processing')
    )
    
    WORKFLOW_TYPE_CHOICES = (
        (WORKFLOW_TYPE_DEFAULT, 'Default'),
        (WORKFLOW_TYPE_CUSTOM, 'Custom')
    )
    
    VOICE_ASSISTANT_METHOD_CHOICES = (
        (VOICE_ASSISTANT_METHOD_OPENAI_REALTIME, 'Openai Realtime API'),
        (VOICE_ASSISTANT_METHOD_WORKFLOW, 'Workflow')
    )

    LONG_TERM_MEMORY_VECTOR_STORAGE_CHOICES = (
        (LONG_TERM_MEMORY_VECTOR_STORAGE_NEO4J, 'Neo4j'),
        (LONG_TERM_MEMORY_VECTOR_STORAGE_QDRANT, 'Qdrant')
    )

    name = models.CharField(max_length=100, blank=True)
    application_type = models.CharField(max_length=100, choices=APPLICATION_TYPE_CHOICES, blank=True)
    request_medium = models.CharField(max_length=100, choices=RequestMedium.REQUEST_MEDIUM_CHOICES, blank=True)
    phone_number = models.CharField(max_length=100, null=True, blank=True, help_text="Phone number associated with the worfkflow with country code, For Eg : '91XXXXXXXXXX'" )
    auth_credentials = models.JSONField(null=True, blank=True, help_text="Credentials associated with the phone number")
    base_api_url = models.CharField(max_length=100, choices=BaseAPIURL_CHOICES)
    billing_session_type = models.CharField(max_length=100, choices=BILLING_SESSION_TYPE_CHOICES,
                                    default=BILLING_SESSION_TYPE_PER_CALL_ONE_SESSION)
    billing_session_count = models.IntegerField(null=True, blank=True, help_text="Allowed Session Count at Once")
    billing_session_time = models.IntegerField(null=True, blank=True, help_text="Allowed Session Time at Once, 'In Minutes'")
    conversation_session_type = models.CharField(max_length=100, choices=CONVERSATION_SESSION_TYPE_CHOICES,
                                    default=CONVERSATION_SESSION_TYPE_TIME_BASED_SESSION)
    conversation_session_count = models.IntegerField(null=True, blank=True, help_text="Specify the maximum number of messages allowed in a single conversation session. Enter '0' for unlimited messages.")
    conversation_session_time = models.IntegerField(null=True, blank=True, help_text="Specify the maximum time allowed between messages in a single conversation session, measured in minutes.")
    conversation_session_refresh_keyword = models.CharField(max_length=20, null=True, blank=True, help_text="Enter a keyword or multiple comma-separated keywords (e.g. :  hello or hello, hi) that will trigger a context refresh for the LLM." )
    enabled_summary_of_chat_history = models.BooleanField(default=False, help_text="Enable or disable the generation of a summary for chat history after a certain number of messages.")
    summary_generation_trigger_limit = models.IntegerField(null=True, blank=True, help_text="The maximum number of messages allowed in chat history before generating a summary.")
    messages_to_keep_in_chat_history_after_summarization = models.IntegerField(null=True, blank=True, help_text="The number of most recent messages to retain in chat history after summarization. Older messages will be removed.")
    enabled_tools_in_chat_history = models.BooleanField(default=False, help_text="Adds/Omits tool messages in chat history supplied to the LLM")
    enabled_long_term_memory_generation = models.BooleanField(default=False, help_text="Enable or disable the generation of long term memories")
    vector_storage_for_long_term_memory = models.CharField(max_length=100, choices=LONG_TERM_MEMORY_VECTOR_STORAGE_CHOICES,
                                    default=LONG_TERM_MEMORY_VECTOR_STORAGE_NEO4J, help_text="Add credentials for accessing storage in company settings")
    required_parameters = models.JSONField(default=dict, blank=True)
    api_route = models.SlugField(max_length=200)
    graph_json = models.JSONField(null=True, blank=True)
    workflow_type = models.CharField(max_length=100, choices=WORKFLOW_TYPE_CHOICES)
    workflow_stream = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    enabled_media_in_chat_history = models.BooleanField(default=False, help_text=" Enables Images/documents etc to be stored as base 64 in Chat History Cache")
    
    voice_assistant_method = models.CharField(max_length=100, choices=VOICE_ASSISTANT_METHOD_CHOICES, blank=True, help_text="select method for voice assistant(workflow/openai_realtime_api)")
    voice_assistant_interruption = models.BooleanField(default=True, help_text="Enable/Disable voice assistant interruption during AI is speaking")

    def __str__(self):
        return f"{self.api_route}"

    @property
    def is_tools_in_chat_history_enabled(self):
        return self.enabled_tools_in_chat_history
    
    @property
    def is_summary_of_chat_history_enabled(self):
        return self.enabled_summary_of_chat_history
    
    @property
    def is_long_term_memory_generation_enabled(self):
        return self.enabled_long_term_memory_generation

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "application_type": self.application_type,
            "request_medium": self.request_medium,
            "phone_number": self.phone_number,
            "auth_credentials": self.auth_credentials,
            "base_api_url": self.base_api_url,
            "billing_session_type": self.billing_session_type,
            "billing_session_count": self.billing_session_count,
            "billing_session_time": self.billing_session_time,
            "conversation_session_type": self.conversation_session_type,
            "conversation_session_count": self.conversation_session_count,
            "conversation_session_time": self.conversation_session_time,
            "conversation_session_refresh_keyword": self.conversation_session_refresh_keyword,
            "enabled_summary_of_chat_history": self.enabled_summary_of_chat_history,
            "summary_generation_trigger_limit": self.summary_generation_trigger_limit,
            "messages_to_keep_in_chat_history_after_summarization": self.messages_to_keep_in_chat_history_after_summarization,
            "enabled_tools_in_chat_history": self.enabled_tools_in_chat_history,
            "enabled_long_term_memory_generation": self.enabled_long_term_memory_generation,
            "vector_storage_for_long_term_memory": self.vector_storage_for_long_term_memory,
            "required_parameters": self.required_parameters,
            "api_route": self.api_route,
            "graph_json": self.graph_json,
            "workflow_type": self.workflow_type,
            "workflow_stream": self.workflow_stream,
            "active": self.active,
            "enabled_media_in_chat_history": self.enabled_media_in_chat_history,
            "voice_assistant_method": self.voice_assistant_method,
            "voice_assistant_interruption": self.voice_assistant_interruption,
            "company_id": self.company_id,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.id = data.get("id")
        obj.name = data.get("name")
        obj.application_type = data.get("application_type")
        obj.request_medium = data.get("request_medium")
        obj.phone_number = data.get("phone_number")
        obj.auth_credentials = data.get("auth_credentials")
        obj.base_api_url = data.get("base_api_url")
        obj.billing_session_type = data.get("billing_session_type")
        obj.billing_session_count = data.get("billing_session_count")
        obj.billing_session_time = data.get("billing_session_time")
        obj.conversation_session_type = data.get("conversation_session_type")
        obj.conversation_session_count = data.get("conversation_session_count")
        obj.conversation_session_time = data.get("conversation_session_time")
        obj.conversation_session_refresh_keyword = data.get("conversation_session_refresh_keyword")
        obj.enabled_summary_of_chat_history = data.get("enabled_summary_of_chat_history")
        obj.summary_generation_trigger_limit = data.get("summary_generation_trigger_limit")
        obj.messages_to_keep_in_chat_history_after_summarization = data.get("messages_to_keep_in_chat_history_after_summarization")
        obj.enabled_tools_in_chat_history = data.get("enabled_tools_in_chat_history")
        obj.enabled_long_term_memory_generation = data.get("enabled_long_term_memory_generation")
        obj.vector_storage_for_long_term_memory = data.get("vector_storage_for_long_term_memory")
        obj.required_parameters = data.get("required_parameters")
        obj.api_route = data.get("api_route")
        obj.graph_json = data.get("graph_json")
        obj.workflow_type = data.get("workflow_type")
        obj.workflow_stream = data.get("workflow_stream")
        obj.active = data.get("active")
        obj.enabled_media_in_chat_history = data.get("enabled_media_in_chat_history")
        obj.voice_assistant_method = data.get("voice_assistant_method")
        obj.voice_assistant_interruption = data.get("voice_assistant_interruption")
        obj.company_id = data.get("company_id")
        
        return obj

    class Meta:
        db_table = 'api_controller_api_controller'
        verbose_name = "ApiController"
        verbose_name_plural = "ApiController"
