from django.db import models
from basics.models import BaseModel, BaseModelCompleteUserTimestamps
from company.models import CompanyBaseModel


class Service(BaseModelCompleteUserTimestamps, CompanyBaseModel):
    SERVICE_TYPE_API = "api"
    SERVICE_TYPE_WEBHOOK = "webhook"

    SCHEDULE_TYPE_NONE = "none"
    SCHEDULE_TYPE_HOURLY = "hourly"
    SCHEDULE_TYPE_MIDNIGHT = "mid_night"

    SERVICE_TYPE_CHOICES = (
        (SERVICE_TYPE_API, "API"),
        (SERVICE_TYPE_WEBHOOK, "Webhook"),
    )

    SCHEDULE_TYPE_CHOICES = (
        (SCHEDULE_TYPE_NONE, "None"),
        (SCHEDULE_TYPE_HOURLY, "Hourly"),
        (SCHEDULE_TYPE_MIDNIGHT, "Mid Night"),
    )
    name = models.CharField(max_length=200)
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, null=True, blank=True,
                                related_name="company_service", verbose_name="Company")

    service_type = models.SlugField(choices=SERVICE_TYPE_CHOICES, max_length=200)
    schedule = models.SlugField(choices=SCHEDULE_TYPE_CHOICES, max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "service_services"
        verbose_name = 'Service'
        verbose_name_plural = 'Services'


class APIEndpoint(BaseModelCompleteUserTimestamps, CompanyBaseModel):
    ENDPOINT_TYPE_GET_API = "get_api"
    ENDPOINT_TYPE_POST_API = "post_api"
    ENDPOINT_TYPE_WEBHOOK = "webhook"

    PRE_PROCESSOR_DEFAULT = "default"

    POST_PROCESSOR_DEFAULT = "default"
    POST_PROCESSOR_KindLife_GET_Order_Processor = "KindLifeGETOrderProcessor"

    ENDPOINT_TYPE_CHOICES = (
        (ENDPOINT_TYPE_GET_API, "GET API"),
        (ENDPOINT_TYPE_POST_API, "POST API"),
        (ENDPOINT_TYPE_WEBHOOK, "Webhook"),
    )

    POST_PROCESSOR_CHOICES = (
        (POST_PROCESSOR_DEFAULT, "Default"),
        (POST_PROCESSOR_KindLife_GET_Order_Processor, "KindLife GET Order Processor"),
    )

    PRE_PROCESSOR_CHOICES = (
        (PRE_PROCESSOR_DEFAULT, "Default"),
    )

    name = models.CharField(max_length=200)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, null=True, blank=True,
                                related_name="company_service_endpoint", verbose_name="Company")
    slug = models.SlugField(max_length=200, unique=True)
    endpoint_type = models.SlugField(choices=ENDPOINT_TYPE_CHOICES, max_length=200)
    endpoint_headers = models.JSONField(default=dict, null=True, blank=True)
    endpoint_token = models.CharField(max_length=200, null=True, blank=True)
    endpoint_url = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    """
      - mapping payload is to store our available keys corresponding with api payload key
      - request payload is to store api, webhook request payload
      - status master store our api status with api vendor api statuses
      - preprocessor is going to store class name by which api pre processing is to be processed
      - postprocessor is going to store class name by which api post processing is to be processed
    """
    mapping_payload = models.JSONField(default=dict, null=True, blank=True)
    request_payload = models.JSONField(default=dict, null=True, blank=True)
    status_master = models.JSONField(default=dict, null=True, blank=True)
    preprocessor = models.SlugField(choices=PRE_PROCESSOR_CHOICES, max_length=200,
                                                null=True, blank=True)
    postprocessor = models.SlugField(choices=POST_PROCESSOR_CHOICES, max_length=200,
                                                null=True, blank=True)



    def __str__(self):
        return self.name

    class Meta:
        db_table = "service_api_endpoint"
        verbose_name = 'Service Endpoint'
        verbose_name_plural = 'Service Endpoints'
