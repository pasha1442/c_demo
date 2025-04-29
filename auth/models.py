import datetime
import random

import pytz
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.models import AbstractUser

from backend.logger import Logger
from basics.utils import UUID
from django.utils import timezone

error_log = Logger(Logger.ERROR_LOG)


class User(AbstractUser):
    USERNAME_FIELD = 'username'
    mobile_number = models.CharField(max_length=15, null=True, blank=True, validators=[
        RegexValidator(regex=r'^\+?\d{7,15}$', message="Enter a valid mobile number.")])
    available_companies = models.ManyToManyField('company.Company')
    current_company = models.ForeignKey('company.Company', on_delete=models.DO_NOTHING,
                                        null=True, blank=True,
                                        related_name="user_current_company", verbose_name="Company")
    user_notification_group = models.ManyToManyField('notifications.NotificationGroup', verbose_name="Notification Group",)

    def __str__(self):
        return self.username

    class Meta:
        db_table = "custom_auth_users"
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        permissions = [
            ("can_view_open_meter_link", "Custom: Can view OpenMeter Link"),
            ("can_view_graph_workflow", "Custom: Can view Graph Workflow"),
            ("can_view_conversation_history", "Custom: Can view Conversation History"),
            ("can_view_api_keys", "Custom: Can view API Keys"),
            ("can_view_data_processing_queue_view", "Custom: Can view Data Processing Queues"),
            ("can_view_access_attempts_view", "Custom: Can view Access Attempts"),
            ("can_view_blocked_users_view", "Custom: Can view Blocked Users"),
            ("can_view_health_check_view", "Custom: Can view Health Check View"),
            ("can_access_backend_custom_pages", "Custom: Can access backend Custom Pages"),
        ]


class AccessPolicy(models.Model):
    POLICY_TYPE_API = "api"
    POLICY_TYPE_WEBHOOK = "webhook"

    POLICY_TYPE_CHOICES = (
        (POLICY_TYPE_API, "API"),
        (POLICY_TYPE_WEBHOOK, "Webhook"),
    )
    name = models.CharField(max_length=200)
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, null=True, blank=True,
                                related_name="company_access_policy", verbose_name="Company")
    is_active = models.BooleanField(default=True)
    policy_type = models.SlugField(choices=POLICY_TYPE_CHOICES, max_length=200)
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE, null=True, blank=True)
    current_service_count = models.IntegerField(default=0)
    service_count_allowed = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_policy_created_at")
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_policy_updated_at")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "custom_auth_access_policy"
        verbose_name = 'custom_auth_access_policy'
        verbose_name_plural = 'custom_auth_access_policies'


class OTP(models.Model):
    OTP_ACCESS_LIMIT = 3
    OTP_EXPIRED_IN_MINUTE = 5
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, null=True, blank=True,
                                related_name="company_otp", verbose_name="Company")
    mobile_number = models.CharField(max_length=15, null=True, blank=True, validators=[
        RegexValidator(regex=r'^\+?\d{7,15}$', message="Enter a valid mobile number.")])
    email_id = models.EmailField(null=True, blank=True, default=None)
    notification_type = models.CharField(max_length=50)
    request_id = models.CharField(max_length=50)
    otp = models.CharField(max_length=10)
    is_otp_used = models.BooleanField(default=False)
    access_attempts = models.IntegerField(default=0)
    is_blacklisted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "custom_auth_otp"
        verbose_name = "OTP"
        verbose_name_plural = "OTP"

    @classmethod
    def is_valid_otp(cls, request_id, otp, email_id, mobile_number):
        """
        Verifies the OTP based on request_id and recipient (mobile/email).
        Marks it as verified if valid.
        """

        # Check for OTP entry
        otp_object = cls.objects.filter(request_id=request_id).first()

        if not otp_object:
            return {"status": False, "message": "Invalid Request ID."}

        otp_object.access_attempts = otp_object.access_attempts + 1

        if otp_object.is_otp_used:
            return {"status": False, "message": "This OTP has already been verified."}

        if otp_object.is_blacklisted:
            return {"status": False, "message": "This OTP is no longer valid. Please try with a new OTP."}

        if otp_object.access_attempts > cls.OTP_ACCESS_LIMIT:
            otp_object.is_blacklisted = True
            otp_object.save()
            return {"status": False, "message": "You have exceed the verification limit."}

        if otp_object.email_id not in [email_id] and otp_object.mobile not in [mobile_number]:
            otp_object.access_attempts = otp_object.access_attempts + 1
            otp_object.save()
            return {"status": False, "message": "Either mobile number or email id is invalid."}

        if otp_object.otp != otp:
            otp_object.save()
            return {"status": False, "message": "You have entered invalid OTP."}

        #<!------------ Check expiry ------------------------>
        current_datetime = timezone.now()
        if otp_object.expired_at and current_datetime > otp_object.expired_at:
            return {"status": False, "message": "OTP has expired."}

        # Mark OTP as verified
        otp_object.is_otp_used = True
        otp_object.save()

        return {"status": True, "message": "OTP verified successfully."}

    @staticmethod
    def generate_otp(mobile_number, email_id, notification_type):
        try:
            otp = str(random.randint(100000, 999999))  # 6-digit OTP
            request_id = UUID.get_uuid4()

            expired_at = datetime.datetime.now() + datetime.timedelta(minutes=OTP.OTP_EXPIRED_IN_MINUTE)
            otp_instance = OTP(
                notification_type=notification_type,
                request_id=request_id,
                otp=otp,
                expired_at=expired_at,
                mobile_number=mobile_number if mobile_number else None,
                email_id=email_id if email_id else None
            )
            otp_instance.save()
            return True, otp_instance
        except Exception as e:
            error_msg = f"Error while generating OTP: {str(e)}"
            error_log.add(error_msg)
            return False, error_msg
