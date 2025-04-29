from django.contrib import admin
from services.models import Service, APIEndpoint
from basics.admin import BaseModelAdmin
from django.utils.translation import gettext_lazy as _


def duplicate_model(modeladmin, request, queryset):
    for obj in queryset:
        # Duplicate the object
        obj.pk = None  # Set primary key to None to create a new entry
        obj.slug = f"{obj.slug }+1"
        obj.save()

    modeladmin.message_user(request, _("Selected rows have been duplicated successfully."))


duplicate_model.short_description = _("Duplicate selected rows")


@admin.register(Service)
class ServiceAdmin(BaseModelAdmin):
    list_display_links = ('id', 'name', 'company', 'service_type', 'schedule', 'is_active', 'created_at', 'created_by')
    list_display = ('id', 'name', 'company', 'service_type', 'schedule', 'is_active', 'created_at', 'created_by')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at', "created_by", "updated_by")
    search_fields = ('name', 'company__name')
    ordering = ('id',)
    fields = (
        'name', 'company', 'service_type', 'schedule', 'is_active', 'created_by', 'updated_by', 'created_at',
        'updated_at')


@admin.register(APIEndpoint)
class APIEndpointAdmin(BaseModelAdmin):
    list_display_links = ('id', 'name', 'company', 'service', 'slug', 'endpoint_type', 'is_active', 'preprocessor', 'postprocessor', 'created_at', 'created_by')
    list_display = ('id', 'name', 'company', 'service', 'slug', 'endpoint_type', 'is_active', 'preprocessor', 'postprocessor', 'created_at', 'created_by')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at', "created_by", "updated_by")
    search_fields = ('name', 'service__name', 'company__name')
    ordering = ('id',)
    actions = [duplicate_model]
    fields = (
        'name', 'company', 'service', 'slug', 'endpoint_type', 'endpoint_token', 'endpoint_url', 'endpoint_headers', 'is_active',
        'preprocessor', 'postprocessor',
        'mapping_payload', 'request_payload', 'status_master',
        'created_by', 'updated_by', 'created_at', 'updated_at')
