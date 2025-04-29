import json

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models

from auth.models import User
from basics.models import BaseModelCompleteUserTimestamps
from company.models import CompanyBaseModel


# Create your models here.

class NotificationTemplates(BaseModelCompleteUserTimestamps):
    WHATSAPP_TEMPLATE = 'whatsapp_template'
    EMAIL_TEMPLATE = 'email_template'
    MESSAGE_TEMPLATE = 'message_template'

    NOTIFICATION_TYPE_EMAIL = "email"
    NOTIFICATION_TYPE_WHATSAPP = "whatsapp"
    NOTIFICATION_TYPE_SMS = "sms"

    TEMPLATE_TYPE_SLUG_CHOICES = (
        (WHATSAPP_TEMPLATE, "Whatsapp Template"), (EMAIL_TEMPLATE, "Email Template"),
        (MESSAGE_TEMPLATE, "SMS Template"))
    NOTIFICATION_TYPE = (
        (NOTIFICATION_TYPE_WHATSAPP, "Whatsapp"), (NOTIFICATION_TYPE_EMAIL, "Email"), (NOTIFICATION_TYPE_SMS, "SMS"))

    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, null=True, blank=True,
                                related_name="company_notification_templates", verbose_name="Company")
    slug = models.SlugField(choices=TEMPLATE_TYPE_SLUG_CHOICES, default=WHATSAPP_TEMPLATE, blank=True, max_length=50)
    notification_type = models.CharField(choices=NOTIFICATION_TYPE, default=NOTIFICATION_TYPE_WHATSAPP, blank=True,
                                         max_length=50)
    title = models.CharField(max_length=250, null=True, blank=True)
    body = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification_templates"
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"

    def __str__(self):
        return dict(self.TEMPLATE_TYPE_SLUG_CHOICES).get(self.slug)


class NotificationGroup(BaseModelCompleteUserTimestamps):
    name = models.CharField(max_length=250, default=None, blank=True)

    class Meta:
        db_table = 'notifications_notification_group'
        verbose_name = "Notification Group"
        verbose_name_plural = "Notification Groups"

    def __str__(self):
        return self.name


class Notification(BaseModelCompleteUserTimestamps):
    NOTIFICATION_TYPES = NotificationTemplates.NOTIFICATION_TYPE  # Notification type is multiple select in order to send same notification on multiple plateforms
    notification_type = models.JSONField(default=None, blank=True)
    notification_group = models.ManyToManyField(NotificationGroup, verbose_name="Notification Group")
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    recipients_list = models.JSONField(blank=True, default=dict)
    recipients_status = models.JSONField(blank=True, default=dict)

    class Meta:
        db_table = 'notifications_notification'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"Notification"

    # def save(self, *args, **kwargs):
    #     print(json.dumps(self.__dict__, indent=4, default=str))  # Pretty-print JSON
    #     if self.notificationgroup:
    #         users = User.objects.filter(notificationgroup__in=self.notificationgroup, is_active=True)
    #         print("users", users)
    #         self.recipients_list = {
    #             "sms": [user.mobile_number for user in users if hasattr(user, 'mobile_number')],
    #             "whatsapp": [user.mobile_number for user in users if hasattr(user, 'mobile_number')],
    #             "email": [user.email for user in users]
    #         }
    #         self.recipients_status = {
    #             "sms": {num: {"status": "pending", "sent_at": "", "error": ""} for num in self.recipients_list["SMS"]},
    #             "whatsapp": {num: {"status": "pending", "sent_at": "", "error": ""} for num in
    #                          self.recipients_list["whatsapp"]},
    #             "email": {email: {"status": "pending", "sent_at": "", "error": ""} for email in
    #                       self.recipients_list["email"]}
    #         }
    #     else:
    #         raise ValidationError({'notificationgroup': 'This field is also required.'})
    #
    #     super().save(*args, **kwargs)
