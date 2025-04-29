from django.contrib import admin
from django import forms
from .models import ApiController
from basics.admin import BaseModelAdmin


@admin.register(ApiController)
class ApiControllerAdmin(BaseModelAdmin):
    list_filter = ('workflow_stream',)
    list_display = (
        'id', 'name', 'complete_url', 'billing_session_type', 'base_api_url', 'api_route', 'billing_session_count', 'billing_session_time',
        'is_active', 'workflow_stream', 'created_at', 'created_by')
    list_display_links = (
        'id', 'name', 'billing_session_type', 'base_api_url', 'is_active', 'workflow_stream', 'created_at', 'created_by')
    search_fields = ('name', 'api_route')
    fields = ('name', 'request_medium', 'phone_number', 'auth_credentials', 'application_type',
              'base_api_url', 'api_route',
              'billing_session_type', 'billing_session_count', 'billing_session_time',
              'conversation_session_type', 'conversation_session_count', 'conversation_session_time',
              'conversation_session_refresh_keyword',
              'enabled_tools_in_chat_history',
              'enabled_summary_of_chat_history',
              'summary_generation_trigger_limit',
              'messages_to_keep_in_chat_history_after_summarization',
              'enabled_long_term_memory_generation',
              'enabled_media_in_chat_history',
              'vector_storage_for_long_term_memory',
              'required_parameters', 'graph_json', 'workflow_type', 'workflow_stream',
              'voice_assistant_method', 'voice_assistant_interruption', 'is_active',
              'created_at', 'created_by', 'updated_at', 'updated_by')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    list_editable = ("api_route",)
    actions = ["duplicate_selected"]

    change_form_template = "admin/api_controller/change_form.html"

    def complete_url(self, obj):
        return f"{obj.base_api_url}{obj.api_route}/"


    def duplicate_selected(self, request, queryset):
        for obj in queryset:
            # Exclude the primary key to create a new object
            obj.pk = None

            # List of unique fields to handle
            unique_fields = ['name', 'api_route']

            for field in unique_fields:
                if hasattr(obj, field):
                    original_value = getattr(obj, field)
                    new_value = f"{original_value}-copy"

                    # To verify that the new value is unique
                    model_class = obj.__class__
                    counter = 1
                    while model_class.objects.filter(**{field: new_value}).exists():
                        new_value = f"{original_value}-copy-{counter}"
                        counter += 1

                    setattr(obj, field, new_value)

            try:
                obj.save()
            except Exception as e:
                # Log or notify the user if the duplication failed
                self.message_user(request, f"Could not duplicate {obj}: {e}", level="error")

    duplicate_selected.short_description = "Duplicate selected %(verbose_name_plural)s"

    class Media:
        js = ('js/admin/api_controller/api_controller.js',)
