from django.db import models
from django.utils.translation import gettext_lazy as _
from basics.models import BaseModel, BaseModelCompleteUserTimestamps


class SystemSetting(BaseModel):
    TYPE_WEB = "web"
    Type_AI_MODEL = "ai_model"

    TYPE_SLUG_CHOICES = (
        (TYPE_WEB, "WEB"),
        (Type_AI_MODEL, "AI Model"),
    )
    SYSTEM_WHATSAPP_MOBILE_NUMBER = 'system_whatsapp_mobile_number'
    SYSTEM_COMPANY_ID = 'system_company_id'
    SYSTEM_USER_ID = 'system_user_id'

    type = models.SlugField(choices=TYPE_SLUG_CHOICES, default=TYPE_WEB, max_length=50)
    key = models.SlugField(max_length=255)
    value = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    @classmethod
    def get_config(self, key):
        config = self.objects.filter(key=key).first()
        return config.value if config else None

    def __str__(self):
        return str(self.key) if self.key else str(self.id)

    class Meta:
        db_table = "system_setting_system_settings"
        verbose_name = _('System Setting')
        verbose_name_plural = _('System Settings')


class DataProcessingQueue(BaseModelCompleteUserTimestamps):
    name = models.CharField(max_length=200)
    queue_name = models.SlugField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "system_settings_data_processing_queues"
        verbose_name = 'Data Processing Queue'
        verbose_name_plural = 'Data Processing Queues'
