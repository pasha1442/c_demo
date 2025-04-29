from django.contrib.auth import get_user_model
from django.db import models
from django.conf import settings

from basics.utils import UUID
from company.models import CompanyBaseModel
from company.utils import CompanyUtils

User = get_user_model()


class Service(CompanyBaseModel):
    name = models.CharField(max_length=100, unique=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name


class ClientSession(CompanyBaseModel):
    token = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.token}"  # type: ignore


class ApiKey(CompanyBaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    key = models.CharField(max_length=255, unique=True, blank=True)
    usage = models.IntegerField(default=0)
    grant = models.IntegerField(default=0)
    expired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.key

    def generate_api_key(self, company=None):
        if not company:
            company = CompanyUtils.get_company_from_company_id(self.company_id) if self.company_id else None
        _token = UUID.get_uuid4()
        api_key = f"{company.prefix}-{_token}"
        return api_key

    def save(self, *args, **kwargs):
        # If the key is not provided, generate a new one
        if not self.key:
            self.key = self.generate_api_key()
        super().save(*args, **kwargs)


class ApiKeyProxyModel(ApiKey):
    objects = models.Manager()

    class Meta:
        proxy = True
        verbose_name = 'API Key'
        verbose_name_plural = 'API Key'
