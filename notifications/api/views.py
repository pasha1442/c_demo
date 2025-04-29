import datetime

from django.http import JsonResponse
from rest_framework import status

from basics.api import api_response_codes
from basics.api.views import BaseModelViewSet
from basics.utils import DateTimeConversion
from notifications.models import Notification, NotificationTemplates
from notifications.services.service import NotificationServices


class NotificationGroupManager(BaseModelViewSet):

    def send_group_notification(self, request):
        request_data = request.data
        notification_id = request_data.get("notification_id")
        if notification_id:
            notification_instance = Notification.objects.get(id=notification_id, is_active=True)
            if notification_instance:
                title = notification_instance.title
                body = notification_instance.body
                recipients_list = notification_instance.recipients_list
                recipients_status = notification_instance.recipients_status
                data_dict = {"notification_type": None, "mobile_number": None, "email_id": None, "title": title,
                             "body": body}
                for notification_type, recipients in recipients_list.items():
                    data_dict["notification_type"] = notification_type
                    status_dict = {}
                    for notification_contact in recipients:
                        notification_contact = str(notification_contact)
                        is_notification_sent = False
                        email_id = None
                        mobile_number = None
                        if notification_contact and notification_type == NotificationTemplates.NOTIFICATION_TYPE_EMAIL:
                            email_id = notification_contact

                        elif notification_contact and notification_contact != 'null':
                            mobile_number = notification_contact

                        if mobile_number or email_id:
                            data_dict["email_id"] = email_id
                            data_dict["mobile_number"] = mobile_number
                            response = NotificationServices(notification_type=notification_type).send_notification(
                                data_dict)
                            message = ""
                            if response.get("status"):
                                is_notification_sent = True
                            else:
                                message = response.get("message")
                        else:
                            message = "Notification contact info missing."

                        if notification_type in recipients_status and notification_contact in recipients_status[
                            notification_type]:
                            recipients_status[notification_type][notification_contact][
                                "status"] = "success" if is_notification_sent else "error"
                            recipients_status[notification_type][notification_contact]["error"] = message
                            recipients_status[notification_type][notification_contact][
                                "sent_at"] = datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S")

                        response_dict = {notification_contact: {"error": message, "status": is_notification_sent,
                                                                "sent_at": DateTimeConversion.to_string(
                                                                    datetime.datetime.now())}}
                        status_dict.update(response_dict)

                if recipients_status and notification_instance:
                    notification_instance.recipients_status = recipients_status
                    notification_instance.save()
                return self.success_response(data={"status": True}, message="Notification sent successfully",
                                             status_code=status.HTTP_200_OK)
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message="Notification record not found.",
                                         status_code=status.HTTP_400_BAD_REQUEST)

        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA, message="Invalid data",
                                     status_code=status.HTTP_400_BAD_REQUEST)
