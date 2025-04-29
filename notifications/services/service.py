import datetime
import json
import random
import firebase_admin
from firebase_admin import messaging

from firebase_admin import auth

from auth.models import OTP
from backend.constants import KAFKA_GLOBAL_WHATSAPP_RESPONSE_MESSAGE_QUEUE
from backend.logger import Logger
from backend.services.kafka_service import BaseKafkaService
from basics.utils import UUID
from notifications.models import NotificationTemplates
from systemsetting.models import SystemSetting

error_log = Logger(Logger.ERROR_LOG)


class NotificationServices():
    DEFAULT_MESSAGE = "Default Message"

    def __init__(self, notification_type):
        self.notification_type = notification_type
        self.notification_map = {
            NotificationTemplates.NOTIFICATION_TYPE_WHATSAPP: WhatsAppNotification(),
            NotificationTemplates.NOTIFICATION_TYPE_SMS: SMSNotification(),
            NotificationTemplates.NOTIFICATION_TYPE_EMAIL: EmailNotification(),
        }

    @staticmethod
    def get_system_settings_by_key(setting_key=None):
        system_setting_object = SystemSetting.objects.filter(key=setting_key, is_active=True).first()
        if system_setting_object:
            return system_setting_object.value, "Success"
        return None, f"System setting not found for key {setting_key}"

    def get_template(self, requested_data):
        """Fetch the notification template based on type and company."""
        notification_type = requested_data.get("notification_type")
        template_instance = NotificationTemplates.objects.filter(notification_type=notification_type,
                                                                 is_active=True).first()
        if not template_instance:
            return False, f"Template not found for notification type {notification_type}"

        title = (template_instance.title).format(**requested_data) if template_instance.title else self.DEFAULT_MESSAGE
        body = (template_instance.body).format(**requested_data) if template_instance.body else self.DEFAULT_MESSAGE

        return True, {"title": title, "body": body}

    def send_notification(self, data_dict={}):
        notification_type = data_dict.get("notification_type")
        mobile_number = data_dict.get("mobile_number")
        email_id = data_dict.get("email_id")
        title = data_dict.get("title")
        body_message = data_dict.get("body")

        # Send notification
        notification_instance = self.notification_map.get(notification_type)
        if not notification_instance:
            error_log.add(f"Invalid notification type: {notification_type}")
            return {"request_id": None, "message": f"Invalid notification type: {notification_type}"}

        response = notification_instance.send(mobile_number=mobile_number, email_id=email_id, title=title,
                                              body_message=body_message)
        return response


class WhatsAppNotification:
    WHATSAPP_REQUEST_PAYLOAD = {"mobile_number": "", "message": "", "template_id": "", "media": "", "button_url": "",
                                "button_type": "", "content_type": "", "parameters": [], "footer_content": "",
                                "whatsapp_provider": "whatsapp_meta", "company_phone_number": "",
                                "company_id": None, "request_id": ""}

    def send(self, mobile_number=None, email_id=None, title=None, body_message=None):
        response = {}
        system_company_mobile_no, response_message = NotificationServices.get_system_settings_by_key(
            SystemSetting.SYSTEM_WHATSAPP_MOBILE_NUMBER)
        if not system_company_mobile_no:
            return {"status": False, "message": response_message}

        system_company_id, response_message = NotificationServices.get_system_settings_by_key(
            SystemSetting.SYSTEM_COMPANY_ID)
        if not system_company_id:
            return {"status": False, "message": response_message}

        if mobile_number:
            try:
                whatsapp_template = self.WHATSAPP_REQUEST_PAYLOAD
                whatsapp_template["message"] = body_message
                whatsapp_template["mobile_number"] = mobile_number
                whatsapp_template["company_phone_number"] = system_company_mobile_no
                whatsapp_template["company_id"] = system_company_id

                notification_response = BaseKafkaService(topic_name=KAFKA_GLOBAL_WHATSAPP_RESPONSE_MESSAGE_QUEUE).push(
                    message=whatsapp_template)
                # if notification_response:
                return {"status": True, "message": "WhatsApp notification sent successfully."}

            except Exception as e:
                error_log.add(f"Something went wrong while sending whatsapp notification. {str(e)}")
                return {"status": False, "message": f"Something went wrong. {str(e)}"}

        return {"status": False, "message": "For WhatsApp notification, a mobile number is required, but an email ID "
                                            "was provided instead."}


class SMSNotification:
    def send(self, mobile_number=None, email_id=None, title=None, body_message=None):
        # Logic to send SMS notification
        try:
            # message = messaging.Message(
            #     notification=messaging.Notification(
            #         title="Your OTP Code",
            #         body=body_message
            #     ),
            #     token=str("0BinyX3wUPRgf2wMDUP6gLTORHt1"),  # Replace with Firebase token for SMS
            # )
            #
            # # Send the message using Firebase
            # response = messaging.send(message)
            response = "SMS Notification sent successfully"
            print(response)
            return {"status": True, "message": "SMS notification sent successfully."}
        except Exception as e:
            raise e


class EmailNotification:
    def send(self, mobile_number=None, email_id=None, title=None, body_message=None):
        # Logic to send Email notification
        print(f"Sending Email to {email_id}: {body_message}")
        return {"status": True, "message": "Email notification sent successfully."}
