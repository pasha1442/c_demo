from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html

from basics.admin import BaseModelAdmin, BaseModelCompleteUserTimestampsAdmin
from systemsetting.models import SystemSetting, DataProcessingQueue


@admin.register(SystemSetting)
class SystemSettingModelAdmin(BaseModelAdmin):
    list_display = ('type', 'key', 'value', 'created_at', 'updated_at')
    list_filter = ('type',)
    readonly_fields = ('deleted_at', 'created_at', 'updated_at')
    fields = ('type', 'key', 'value', 'is_active', 'is_deleted', 'deleted_at', 'created_at', 'updated_at')


@admin.register(DataProcessingQueue)
class DataProcessingQueueAdmin(BaseModelCompleteUserTimestampsAdmin):
    list_display_links = ('id', 'name', 'queue_name', 'is_active', 'created_at', 'created_by')
    list_display = ('id', 'name', 'queue_name', 'queue_count', 'failure_queue', 'is_active', 'created_at', 'created_by')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at', "created_by", "updated_by")
    search_fields = ('name', 'queue_name')
    ordering = ('id',)
    fields = ('name', 'queue_name', 'is_active', 'created_at', 'updated_at', 'created_by', 'updated_by')

    change_list_template = 'admin/data_processing_queue/change_list.html'

    def queue_count(self, obj):
        return format_html(
            """<span id="queue-count-{}">Loading...</span>""",obj.queue_name,
        )
    queue_count.short_description = 'Queue Count'

    def failure_queue(self, obj):
        _queue_name = f"failure_{str(obj.queue_name)}"
        return format_html(
            """<span id="queue-count-{}">Loading...</span>""",_queue_name,
        )
    failure_queue.short_description = 'Failure Queue'

