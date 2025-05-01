from django.utils import timezone
from tabnanny import verbose
from turtle import update
from uuid import uuid4
from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from pydantic import UUID4
from basics.models import BaseModel, BaseManager
from django.contrib.auth import get_user_model
from django.db.models import Q
from basics.utils import Registry
from backend.constants import CURRENT_USER_ID, CURRENT_API_COMPANY
from datetime import datetime
from django.db.models import Q
from dateutil.relativedelta import relativedelta
from datetime import timedelta

User = get_user_model()


class Company(BaseModel):
    name = models.CharField(max_length=100)
    code = models.UUIDField(default=uuid4, unique=True)
    current_env = models.CharField(max_length=100, null=True, blank=True,
                                   help_text="<env>_<company_name>: Metering Subject")
    frontend_link = models.CharField(max_length=200, null=True, blank=True, verbose_name="Demo Link")
    # workflow_processing_queue = models.ForeignKey(DataProcessingQueue, on_delete=models.DO_NOTHING, null=True, blank=True,
    #                                              verbose_name="WorkFlow Processing Queue")
    langfuse_project_id = models.CharField(max_length=200, null=True, blank=True)
    langfuse_secret_key = models.CharField(max_length=200, null=True, blank=True)
    langfuse_public_key = models.CharField(max_length=200, null=True, blank=True)
    openmeter_secret_key = models.CharField(max_length=200, null=True, blank=True)

    prefix = models.CharField(max_length=10)
    comment = models.CharField(max_length=200, null=True, blank=True)

    is_snooping_enabled = models.BooleanField(
        default=False, 
        verbose_name="Enable Snooping",
        help_text="When enabled, messages will be forwarded to the specified webhook URLs for monitoring purposes."
    )
    
    def __str__(self):
        return f'{self.name}'

    def to_dict(self):
        """Convert Company instance to a serializable dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "code": str(self.code),
            "current_env": self.current_env,
            "prefix": self.prefix,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.id = data.get("id")
        obj.name = data.get("name")
        obj.code = data.get("code")
        obj.current_env = data.get("current_env")
        obj.prefix = data.get("prefix")
        obj.created_at = data.get("created_at")
        obj.updated_at = data.get("updated_at")
        obj.is_active = data.get("is_active")
        obj.is_snooping_enabled = data.get("is_snooping_enabled", False)
        return obj

    class Meta:
        db_table = "company_companies"
        verbose_name = "Company"
        verbose_name_plural = "Companies"


class CompanyBaseManager(BaseManager):
    def __init__(self, *args, **kwargs):
        self.company_filter = kwargs.pop('company_filter', True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if Registry().get(CURRENT_USER_ID) is not None:
            user_id = Registry().get(CURRENT_USER_ID)
            user = User.objects.filter(id=user_id).first()
            company = user.current_company
        elif Registry().get(CURRENT_API_COMPANY) is not None:
            current_company = Registry().get(CURRENT_API_COMPANY)
            if isinstance(current_company, dict):
                company = Company.objects.filter(id=current_company['id']).first()
            else:
                company = current_company
        queryset = super(CompanyBaseManager, self).get_queryset()
        if self.model.__name__ == "Conversations":
            print("---------------------, ", self.model.__name__)
            now = timezone.now()
            #current_month = now.month
            #quarter_start_month = 3 * ((current_month - 1) // 3) + 1
            #quarter_start_date = datetime(now.year, quarter_start_month, 1)
            #quarter_end_date = quarter_start_date + relativedelta(months=3) - relativedelta(days=1)
            #created_at_in_filter = any(
            #    "created_at" in str(condition) for condition in queryset.query.where.children
            #)
            # if not created_at_in_filter:
            #    queryset = queryset.filter(
            #        Q(created_at__gte=quarter_start_date) & Q(created_at__lte=quarter_end_date)
            #    )
            last_90_days_date = now - timedelta(days=90)

            # Check if `created_at` is in the filters
            created_at_in_filter = any(
                "created_at" in str(condition) for condition in queryset.query.where.children
            )

            if not created_at_in_filter:
                queryset = queryset.filter(
                    Q(created_at__gte=last_90_days_date)
                )

        if self.company_filter:
            return queryset.filter(company=company)
        return queryset


class CompanyBaseModel(BaseModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, editable=False)
    objects = CompanyBaseManager()
    all_objects = CompanyBaseManager(alive_only=False)
    without_company_objects = CompanyBaseManager(company_filter=False)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        user_id = Registry().get(CURRENT_USER_ID)
        current_company = Registry().get(CURRENT_API_COMPANY)
        # if self.company:
        #     pass
        # el
        if user_id:
            user = User.objects.filter(id=user_id).first()
            self.company = user.current_company
        elif current_company:
            self.company = current_company
        # from company.admin import company_admin_site
        # self.company_id = company_admin_site.get_company().id
        super().save(force_insert, force_update, using, update_fields)

    class Meta:
        abstract = True


class GlobalMixedCompanyBaseManager(BaseManager):

    def __init__(self, *args, **kwargs):
        self.company_filter = kwargs.pop('company_filter', True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        user_id = Registry().get(CURRENT_USER_ID)
        current_company = Registry().get(CURRENT_API_COMPANY)
        if user_id:
            user = User.objects.filter(id=user_id).first()
            self.company = user.current_company
        elif current_company:
            self.company = current_company
        queryset = super(GlobalMixedCompanyBaseManager, self).get_queryset()
        if self.company_filter:
            return queryset.filter(Q(company=self.company) | Q(is_global=True))
        return queryset


class GlobalMixedCompanyBaseModel(BaseModel):
    is_global = models.BooleanField(default=False, verbose_name='global')
    company = models.ForeignKey(Company, null=True, blank=True, on_delete=models.CASCADE, editable=False)
    objects = GlobalMixedCompanyBaseManager()
    all_objects = GlobalMixedCompanyBaseManager(alive_only=False)
    without_company_objects = GlobalMixedCompanyBaseManager(company_filter=False)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None, company=None):
        if self.is_global:
            pass
        elif self.company:
            pass
        elif company:
            self.company = company
        elif Registry().get(CURRENT_API_COMPANY):
            self.company = Registry().get(CURRENT_API_COMPANY)
        else:
            user_id = Registry().get(CURRENT_USER_ID)
            if user_id:
                user = User.objects.filter(id=user_id).first()
                self.company = user.current_company
        super(GlobalMixedCompanyBaseModel, self).save(force_insert, force_update, using, update_fields)

    class Meta:
        abstract = True


# class CompanyBasePostgresManager(CompanyBaseManager, PostgresManager):
#     def get_queryset(self):
#         return super().get_queryset()


# class CompanyBasePartitionModel(CompanyBaseModel, PostgresPartitionedModel):
#     objects = CompanyBasePostgresManager()

#     class Meta:
#         abstract = Truecompany.CompanyUser.groups

class CompanySetting(GlobalMixedCompanyBaseModel):
    KEY_CHOICE_WHATSAPP_PROVIDER = "whatsapp_provider"
    KEY_CHOICE_KG_NEO4J_CREDENTIALS = "KG_neo4j"
    KEY_CHOICE_KB_SQL_CREDENTIALS = "SQL_DB"
    KEY_CHOICE_KB_BQ_CREDENTIALS = "BQ_DB"
    KEY_CHOICE_VECTOR_DB_PINECONE_CREDENTIALS = "pinecone"
    KEY_CHOICE_VECTOR_DB_QDRANT_CREDENTIALS = "qdrant"
    KEY_CHOICE_TWILLIO_COMPANY_NUMBER = "twillio_company_number"
    KEY_CHOICE_SNOOPING_WEBHOOK_URLS = "snooping_webhook_urls"
    KEY_CHOICE_QUEUE_NAME = "snooping_queue_name"

    KEY_TYPE_CHOICES = (
        (KEY_CHOICE_WHATSAPP_PROVIDER, "WhatsApp Provider"),
        (KEY_CHOICE_KG_NEO4J_CREDENTIALS, "Knowledge Graph Neo4j"),
        (KEY_CHOICE_KB_SQL_CREDENTIALS, "Knowledge Base SQL"),
        (KEY_CHOICE_VECTOR_DB_PINECONE_CREDENTIALS, "Pinecone"),
        (KEY_CHOICE_VECTOR_DB_QDRANT_CREDENTIALS, "Qdrant"),
        (KEY_CHOICE_TWILLIO_COMPANY_NUMBER, "Twillio Company Number"),
        (KEY_CHOICE_KB_BQ_CREDENTIALS, "Knowledge Base Big Query"),
        (KEY_CHOICE_SNOOPING_WEBHOOK_URLS, "Snooping Webhook URLs"),
        (KEY_CHOICE_QUEUE_NAME, "Snooping Queue Name")
    )
    
    key = models.CharField(max_length=100, choices=KEY_TYPE_CHOICES, blank=True)
    value = models.JSONField(default=dict)

    class Meta:
        db_table = "company_settings"
        

class CompanySettingProxyModel(CompanySetting):
    objects = models.Manager()

    class Meta:
        proxy = True
        verbose_name = 'Company Setting'
        verbose_name_plural = 'Company Setting'


class CompanyTest(CompanyBaseModel):
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "company_model_test"


class CompanyUserManager(UserManager):
    # def get_queryset(self):
    #     from company.admin import company_admin_site
    #     qs = super().get_queryset()
    #     active_company = company_admin_site.get_company()

    #     # Filter users based on the active company OR global status, but EXCLUDE superusers
    #     return qs.filter(
    #         Q(company=active_company) | Q(is_global=True),
    #         is_superuser=False # Exclude superusers from the list
    #     )

    # class Meta:
    #     abstract = True
    def get_queryset(self):
        qs = super().get_queryset()
        return qs
    # pass


class CompanyCustomer(GlobalMixedCompanyBaseModel):
    mobile = models.CharField(max_length=128)
    profile_data = models.JSONField(default=dict, null=True)

    class Meta:
        db_table = "company_customers"


class CompanyEntity(GlobalMixedCompanyBaseModel):
    type = models.CharField(max_length=128)
    desc = models.CharField(max_length=256, null=True)
    reference_id = models.CharField(max_length=256, null=False)
    data = models.JSONField(default=dict, null=True)

    class Meta:
        db_table = "company_entities"
        verbose_name = "company_entity"
        verbose_name_plural = "company_entities"


class CompanyPostProcessing(GlobalMixedCompanyBaseModel):
    class ActionChoices(models.IntegerChoices):
        NO_ACTION = 0, 'No Action'
        ACTION_PENDING = 1, 'Action Pending'
        ACTION_COMPLETED = 2, 'Action Completed'

    session_nature = models.CharField(max_length=128)
    session_id = models.CharField(max_length=256)
    client_session_ref_id = models.CharField(max_length=256)
    data = models.JSONField(default=dict, null=True)
    action = models.IntegerField(choices=ActionChoices.choices, default=ActionChoices.NO_ACTION)

    class Meta:
        db_table = "company_post_processing"
