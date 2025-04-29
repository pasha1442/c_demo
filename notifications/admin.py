from django.contrib import admin

from django.utils.html import format_html

from auth.models import User
from basics.admin import BaseModelAdmin
from notifications.forms import NotificationForm
from notifications.models import NotificationTemplates, NotificationGroup, Notification
from notifications.services.admin.service import NotificationAdminServices


# Register your models here.
@admin.register(NotificationTemplates)
class NotificationTemplatesAdminSite(BaseModelAdmin):
    list_display_links = ('id', 'company', 'slug', 'notification_type', 'title', 'body', 'is_active', 'created_at')
    list_display = ('id', 'company', 'slug', 'notification_type', 'title', 'body', 'is_active', 'created_at')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'deleted_at')
    search_fields = ('notification_type', 'slug',)
    ordering = ('id',)
    fields = ('is_active', 'company', 'slug', 'notification_type', 'title', 'body', 'created_at', 'deleted_at')


@admin.register(NotificationGroup)
class NotificationGroupAdminSite(BaseModelAdmin):
    list_display_links = ('id', 'name', 'is_active', 'created_at')
    list_display = ('id', 'name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'deleted_at')
    fields = ( 'name', 'is_active', 'is_deleted', 'created_at', 'deleted_at')



@admin.register(Notification)
class NotificationAdminSite(BaseModelAdmin):
    form = NotificationForm
    list_display_links = (
        'id', 'notification_type_display', 'notification_group_display', 'title', 'body', 'is_active', 'created_at')
    list_display = (
        'id', 'notification_type_display', 'notification_group_display', 'title', 'body', 'is_active', 'created_at')
    list_filter = ('is_active', 'notification_group')

    fieldsets = (
        (None, ({'fields': (
            'notification_group', 'notification_type', 'title', 'body',
            'is_active',
            'is_deleted', 'created_at', 'deleted_at', 'recipients_list_display', 'recipients_status_display')})),
        (('Recipients'), {'fields': ('recipients_list', 'recipients_status',), }),

    )
    readonly_fields = (
        'deleted_at', 'recipients_list_display', 'recipients_status_display', 'recipients_list', 'recipients_status',
        'created_at')

    change_form_template = "admin/notifications/change_form.html"

    def notification_type_display(self, obj):
        """Show notification_type as a comma-separated string in list view"""
        if isinstance(obj.notification_type, list):
            return ", ".join(obj.notification_type)
        return obj.notification_type  # In case it's stored as a string

    def notification_group_display(self, obj):
        return ", ".join([group.name for group in obj.notification_group.all()])

    notification_type_display.short_description = "Notification Type"

    notification_group_display.short_description = "Notification Group"

    def recipients_list_display(self, obj):
        recipients_list = obj.recipients_list
        email_list = recipients_list.get("email", [])
        mobile_list = recipients_list.get("sms", [])
        whatsapp_list = recipients_list.get("whatsapp", [])

        sms_table_html = NotificationAdminServices().get_recipients_list_html_template(mobile_list,
                                                                                       NotificationTemplates.NOTIFICATION_TYPE_SMS)
        whatsapp_table_html = NotificationAdminServices().get_recipients_list_html_template(whatsapp_list,
                                                                                            NotificationTemplates.NOTIFICATION_TYPE_WHATSAPP)
        email_table_html = NotificationAdminServices().get_recipients_list_html_template(email_list,
                                                                                         NotificationTemplates.NOTIFICATION_TYPE_EMAIL)

        return format_html(sms_table_html + whatsapp_table_html + email_table_html)

    def recipients_status_display(self, obj):
        table_html = NotificationAdminServices().get_recipients_status_html_template(obj)
        return format_html(table_html)

    recipients_list_display.short_description = "Recipients List"
    recipients_status_display.short_description = "Recipients Status"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'notification_group' in form.cleaned_data and not obj.recipients_list and not obj.recipients_status:
            obj.notification_group.set(form.cleaned_data['notification_group'])
            notification_groups = form.cleaned_data.get("notification_group", [])

            users = User.objects.filter(user_notification_group__in=notification_groups, is_active=True)
            if users:
                obj.recipients_list = {}
                if NotificationTemplates.NOTIFICATION_TYPE_SMS in obj.notification_type:
                    obj.recipients_list[NotificationTemplates.NOTIFICATION_TYPE_SMS] = [user.mobile_number for user in users if
                                                  hasattr(user, 'mobile_number')]

                if NotificationTemplates.NOTIFICATION_TYPE_WHATSAPP in obj.notification_type:
                    obj.recipients_list[NotificationTemplates.NOTIFICATION_TYPE_WHATSAPP] = [user.mobile_number for user in users if
                                                  hasattr(user, 'mobile_number')]

                if NotificationTemplates.NOTIFICATION_TYPE_EMAIL in obj.notification_type:
                    obj.recipients_list[NotificationTemplates.NOTIFICATION_TYPE_EMAIL] = [user.email for user in users]

                obj.recipients_status = {
                    key: {
                        recipient: {"status": "pending", "sent_at": "", "error": ""}
                        for recipient in obj.recipients_list[key]
                    }
                    for key in obj.recipients_list  # Only create status for existing notification types
                }

        super().save_model(request, obj, form, change)
