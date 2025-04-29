from requests import request
from django.contrib import admin
from django import forms
from .models import Conversations, Prompt, ConversationSession, WorkflowAttributes
from basics.admin import BaseModelAdmin
from rangefilter.filters import DateRangeFilter
from import_export import resources
from import_export.admin import ExportMixin
from import_export.fields import Field


class PromptForm(forms.ModelForm):
    class Meta:
        model = Prompt
        fields = "__all__"


@admin.register(Prompt)
class PromptAdmin(BaseModelAdmin):
    list_display = ('id', 'prompt_type', 'company', 'active', 'version', 'llm', 'model')
    list_display_links = ('id', 'prompt_type', 'company', 'active', 'version', 'llm', 'model')
    search_fields = ('prompt_type',)
    list_filter = ('is_active',)
    fields = ("prompt_type", "version", "active", "is_deleted", "role", "llm", "model", "content", "functions", "deleted_at")
    form = PromptForm
    change_form_template = 'admin/chat/prompt/change_form.html'


class ConversationResource(resources.ModelResource):
    company_name = Field(attribute='company__name', column_name='Company Name')
    request_id = Field(attribute='request_id', column_name='Request ID')
    client_identifier = Field(attribute='client_identifier', column_name='Client Identifier')
    client_session_id = Field(attribute='client_session_id', column_name='Client Session ID')
    session_id = Field(attribute='session_id', column_name='Session ID')   
    billing_session_id = Field(attribute='billing_session_id', column_name='Billing Session ID')
    mobile = Field(attribute='mobile', column_name='Mobile')
    message = Field(attribute='message', column_name='Message')
    role = Field(attribute='role', column_name='Role')
    request_medium = Field(attribute='request_medium', column_name='Request Medium')
    function_name = Field(attribute='function_name', column_name='Function Name')
    message_type = Field(attribute='message_type', column_name='Message Type')
    created_at = Field(attribute='created_at', column_name='Created At')
    
    class Meta:
        model = Conversations
        fields = ('id', 'company_name', 'request_id', 'client_identifier', 'client_session_id', 'session_id', 'billing_session_id', 'mobile', 'message', 'role', 'request_medium', 'function_name', 'message_type', 'message', 'message_id', 'message_metadata', 'created_at')
        export_order = fields

@admin.register(Conversations)
class ConversationsAdmin(ExportMixin, BaseModelAdmin):
    resource_class = ConversationResource
    ordering = ['-created_at']
    list_display = ('id', 'request_id', 'client_identifier', 'mobile', 'client_session_id', 'session_id', 
                   'billing_session_id', 'role', 'request_medium', 'function_name', 'message_type', 
                   'message', 'message_id', 'message_metadata', 'created_at')
    list_filter = (
        'role',
        'client_identifier',
        'request_medium',
        'function_name',
        ('created_at', DateRangeFilter)
    )
    search_fields = ('mobile', 'client_session_id', 'session_id', 'client_identifier', 
                    'billing_session_id', 'request_id')
    fields = ("client_session_id", "session_id", "client_identifier", "mobile", "role", 
             "message_id", "parent_message_id", "function_name", "message", "is_active", 
             "is_deleted", "deleted_at")
    
    def get_export_queryset(self, request):
        queryset = super().get_export_queryset(request)
        created_at_range = request.GET.get('created_at__range', '')
        if created_at_range:
            start_date, end_date = created_at_range.split(',')
            queryset = queryset.filter(created_at__range=(start_date, end_date))
        return queryset.select_related('company')

    class Meta:
        ordering = ['-created_at']

@admin.register(ConversationSession)
class ConversationSessionsAdmin(BaseModelAdmin):
    list_display = ('id', 'client_identifier', 'client_session_id', 'session_id', 'conv_summary', 
                   'request_medium', 'api_controller', 'is_episodic_memory_created', 'created_at')
    search_fields = ('client_identifier', 'session_id')
    fields = ('client_identifier', 'client_session_id', 'session_id', 'conv_summary', 
             'request_medium', 'api_controller', 'ignore_session', 'ai_takeover_session', 
             'is_episodic_memory_created', 'episodic_memory_created_at', 'created_at')
    readonly_fields = ("created_at", 'episodic_memory_created_at', 'api_controller')


@admin.register(WorkflowAttributes)
class WorkflowAttributesAdmin(BaseModelAdmin):
    list_display = ('id', 'name', 'company', 'slug', 'attribute_type', 'is_active', 'created_at')
    search_fields = ('name',)
    fields = ('name', 'company','slug' ,'attribute_type', 'response_formatter_type', 'content', 'is_active', 'created_at', 'created_by', 'updated_at', 'updated_by')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'company')
