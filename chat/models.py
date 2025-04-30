from cmd import PROMPT
import json
from django.db import models
from django.conf import settings
import time

from pydantic import ValidationError
from basics.models import BaseModelCompleteUserTimestamps
from company.models import CompanyBaseModel


def current_timestamp_as_int():
    return int(time.time())


class RequestMedium:
    REQUEST_MEDIUM_WHATSAPP_META = "whatsapp_meta"
    REQUEST_MEDIUM_WHATSAPP_SINCH = "whatsapp_sinch"
    REQUEST_MEDIUM_API = "api"
    REQUEST_MEDIUM_PYTHON_SDK = "python_sdk"
    REQUEST_MEDIUM_JS_SDK = "js_sdk"
    REQUEST_MEDIUM_TWILIO = "twilio"
    REQUEST_MEDIUM_WAHA = "waha"

    REQUEST_MEDIUM_CHOICES = (
        (REQUEST_MEDIUM_WHATSAPP_META, 'Whatsapp Meta Cloud API'),
        (REQUEST_MEDIUM_WHATSAPP_SINCH, 'Whatsapp Sinch API'),
        (REQUEST_MEDIUM_TWILIO, 'Twilio API'),
        (REQUEST_MEDIUM_API, 'API'),
        (REQUEST_MEDIUM_PYTHON_SDK, 'Python SDK'),
        (REQUEST_MEDIUM_JS_SDK, 'JS SDK'),
        (REQUEST_MEDIUM_WAHA, 'WAHA')
    )


class ConversationSession(CompanyBaseModel):
    client_identifier = models.CharField(max_length=256, null=True)
    session_id = models.CharField(max_length=256, default=current_timestamp_as_int)
    client_session_id = models.CharField(max_length=256, null=True, blank=True)
    conv_summary = models.TextField(null=True, blank=True)
    request_medium = models.CharField(max_length=128, default=RequestMedium.REQUEST_MEDIUM_API, null=True, verbose_name='Request Medium')
    ignore_session = models.BooleanField(default=False)
    ai_takeover_session = models.BooleanField(default=False)
    is_episodic_memory_created = models.BooleanField(default=False)
    episodic_memory_created_at = models.DateTimeField(null=True,auto_now=False)
    api_controller = models.ForeignKey(
        'api_controller.ApiController',
        on_delete=models.DO_NOTHING,
        null=True, 
        blank=True
    )
    
    webhook_urls = models.JSONField(null=True, blank=True, default=dict, 
        help_text="Store webhook URLs for different purposes")
    
    message_templates = models.JSONField(default=dict, null=True, blank=True,
                                         help_text="JSON configuration for message templates, e.g. {\"default_nudge\": \"Hey there! Just checking in.\"}")
    
    nudging_threshold_minutes = models.IntegerField(default=60, 
                                                   help_text="Time in minutes before sending a nudge message to inactive users")

    prefix = models.CharField(max_length=10)
    comment = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        db_table = 'chat_conversation_sessions'
        verbose_name = "Conversation Session"
        verbose_name_plural = "Conversation Sessions"
        indexes = [
            models.Index(fields=['company_id'], name='ix_conv_session_company_id'), 
            models.Index(fields=['client_identifier'], name='ix_conv_sess_client_identifier'), 
            models.Index(fields=['company_id', 'created_at'], name='ix_convsesscomidcreated_at'), 
        ]


class Conversations(CompanyBaseModel):
    MESSAGE_TYPE_TEXT_CHOICE = 'text'
    MESSAGE_TYPE_IMAGE_CHOICE = 'image'
    MESSAGE_TYPE_PDF_CHOICE = 'pdf'
    MESSAGE_TYPE_VIDEO_CHOICE = 'video'

    MESSAGE_TYPE_CHOICES = [
        (MESSAGE_TYPE_TEXT_CHOICE, 'Text'),
        (MESSAGE_TYPE_IMAGE_CHOICE, 'Image'),
        (MESSAGE_TYPE_PDF_CHOICE, 'PDF'),
        (MESSAGE_TYPE_VIDEO_CHOICE, 'Video'),
    ]

    message_id = models.CharField(max_length=128, default=None, null=True)
    parent_message_id = models.CharField(max_length=128, default=None, null=True)
    mobile = models.CharField(max_length=128)
    role = models.CharField(max_length=20, default='user', verbose_name='Role')
    function_name = models.CharField(max_length=128, default=None, null=True, verbose_name='Function name')
    message = models.TextField()
    request_medium = models.CharField(max_length=128, default=RequestMedium.REQUEST_MEDIUM_API, null=True,
                                      verbose_name='Request Medium')
    request_id = models.CharField(max_length=256, null=True)
    client_identifier = models.CharField(max_length=256, null=True)
    client_session_id = models.CharField(max_length=256, null=True, blank=True)
    session_id = models.CharField(max_length=256, default=current_timestamp_as_int)
    billing_session_id = models.CharField(max_length=256, null=True)

    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default=MESSAGE_TYPE_TEXT_CHOICE
    )
    message_metadata = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'chat_conversations'
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        indexes = [
            models.Index(fields=['company_id'], name='ix_conv_company_id'), 
            models.Index(fields=['client_identifier'], name='ix_conv_client_identifier'), 
            models.Index(fields=['session_id'], name='ix_conv_session_id'), 
            models.Index(fields=['session_id', 'created_at'], name='ix_conv_sessidcreatedat'), 
        ]


class Prompt(CompanyBaseModel):
    PROMPT_TYPE_MASTER_ASSISTANT = "master_assistant"

    PROMPT_TYPES = (
        (PROMPT_TYPE_MASTER_ASSISTANT, 'Master assistant'),
        ('order_query_assistant', 'Order queries assitant'),
        ('brand_onboarding_assistant', 'Brand onboarding assistant'),
        ('bulk_order_assistant', 'Bulk order assistant'),
        ('corp_gifting_assistant', 'Corporate gifting assistant'),
        ('expert_assistant', 'Expert assistant'),
        ('agent_assistant', 'Agent assistant'),
        ('summary_assistant', 'Summary assistant'),
        ('actionables_assistant', 'Actionables assistant'),
        ('sen_analysis_assistant', 'Sentimental analysis assistant'),
        ('profile_data_extracting_assistant', 'Profile data extraction assistant'),
        ('agent_evaluation_prompt', 'Agent evaluation prompt'),
        ('brand_support_assistant', 'Brand Support Assistant'),
        ('policy_expert_assistant', 'Policy Expert Assistant'),
        ('survey_assistant', 'Survey Assistant')

    )
    ROLE_CHOICES = (
        ('system', 'System prompt'),
        ('assistant', 'Assistant prompt'),
        ('function', 'Function prompt'),
    )
    LLM_CHOICES = (
        ('openai', 'Open AI'),
        ('google', 'Google'),
        ('local', 'Open Source')
    )
    MODEL_CHOICES = (
        ('gpt-4-0125-preview', 'GPT-4'),
        ('gpt-3.5-turbo-1106', 'GPT-3.5'),
        ('gpt-4o', 'GPT-4o'),
        ('gemini-1', 'Gemini-1'),
        ('gemini-1.5', 'Gemini-1.5'),
        ('mistralai/Mistral-7B-Instruct-v0.3', 'Mistral-7B-Instruct'),
        ('microsoft/Phi-3-mini-4k-instruct', 'Phi-3-Mini-4k-Instruct')
    )
    prompt_type = models.CharField(max_length=100, choices=PROMPT_TYPES, default='master_assistant')
    version = models.CharField(max_length=10, default='1.0')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='system')
    llm = models.CharField(max_length=30, choices=LLM_CHOICES, default='openai')
    model = models.CharField(max_length=100, choices=MODEL_CHOICES, default='gpt-4')
    content = models.TextField()
    functions = models.JSONField(default=dict)
    active = models.BooleanField(default=False)

    # def save(self, *args, **kwargs):
    #     if self.active:  # Check if the current instance is marked as active
    #     # Deactivate all other active prompts of the same type for the client and llm
    #         Prompt.objects.filter(
    #             client=self.client, 
    #             prompt_type=self.prompt_type, 
    #             active=True
    #         ).exclude(pk=self.pk).update(active=False)
    #     super(Prompt, self).save(*args, **kwargs)
    def __str__(self):
        return f'{self.get_prompt_type_display()} - {self.company}'

    class Media:
        js = ('js/admin/dynamic_models.js',)


class Function(models.Model):
    prompt = models.ForeignKey(Prompt, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField()


class Parameter(models.Model):
    function = models.ForeignKey(Function, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    description = models.TextField()


class WorkflowAttributes(CompanyBaseModel, BaseModelCompleteUserTimestamps):
    ATTRIBUTE_TYPE_RESPONSE_FORMATTER_CHOICE = 'response_formatter'

    ATTRIBUTE_TYPE_CHOICES = [
        (ATTRIBUTE_TYPE_RESPONSE_FORMATTER_CHOICE, 'Response Formatter')
    ]
    
    RESPONSE_FORMATTER_TYPE_JSON = 'json'
    RESPONSE_FORMATTER_TYPE_XML = 'xml'

    RESPONSE_FORMATTER_TYPE_CHOICES = [
        (RESPONSE_FORMATTER_TYPE_JSON, 'JSON'),
        (RESPONSE_FORMATTER_TYPE_XML, 'XML'),
    ]
    
    name = models.CharField(max_length=128, default=None, null=True, verbose_name='name')
    slug = models.SlugField(max_length=128, default=None, null=True)
    attribute_type = models.CharField(
        max_length=50,
        choices=ATTRIBUTE_TYPE_CHOICES,
        default=ATTRIBUTE_TYPE_RESPONSE_FORMATTER_CHOICE
    )
    
    response_formatter_type = models.CharField(
        max_length=50,
        choices=RESPONSE_FORMATTER_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='Response Formatter Type'
    )
    
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    

    class Meta:
        unique_together = ('company', 'slug')
        
    def clean(self):
        if self.attribute_type == self.ATTRIBUTE_TYPE_RESPONSE_FORMATTER_CHOICE:
            if not self.response_formatter_type:
                raise ValidationError({'response_formatter_type': 'This field is required when attribute_type is response_formatter.'})
            
            if self.response_formatter_type == self.RESPONSE_FORMATTER_TYPE_JSON:
                try:
                    json.loads(self.content)  # Try to parse JSON
                except json.JSONDecodeError:
                    raise ValidationError({'content': 'Invalid JSON format.'})

        else:
            if self.response_formatter_type:
                raise ValidationError({'response_formatter_type': 'This field should be empty unless attribute_type is response_formatter.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
