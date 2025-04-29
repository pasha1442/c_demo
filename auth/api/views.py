from rest_framework import status

from auth.models import OTP
from basics.api.views import BaseModelViewSet, AuthenticationAPIView
from django.contrib.auth import get_user_model
from basics.utils import check_mandatory_values, UUID
from basics.api import api_response_codes
from django.utils.translation import gettext_lazy as _

from notifications.services.service import NotificationServices

User = get_user_model()


class UserApiView(AuthenticationAPIView, BaseModelViewSet):

    def set_current_company(self, request):
        request_data = request.data
        user_id = request.user.id
        company_id = request_data.get('company_id', None)
        _required_values = check_mandatory_values(request_data, ['company_id'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        User.objects.filter(id=user_id).update(current_company_id=company_id)
        return self.success_response(data={}, message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        # return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
        #                              message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})

    def get_user_wise_company_choices(self, request):
        user_id = request.user.id
        query_set = User.objects.filter(id=user_id).first()
        available_companies = query_set.available_companies.all()
        _available_companies = [{a.id: a.name} for a in available_companies]
        return self.success_response(data={"available_companies": _available_companies,
                                           "current_company_id": query_set.current_company_id},
                                     message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)


class UserAuthenticationManager(AuthenticationAPIView, BaseModelViewSet):

    def send_otp(self, request):
        request_args = request.data
        notification_type = request_args.get("notification_type")
        mobile_number = request_args.get("mobile_number")
        email_id = request_args.get("email_id")

        missing_params = check_mandatory_values(request_args, ["notification_type"])
        if missing_params:
            return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                         message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                         data=missing_params)

        if not email_id and not mobile_number:
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message="At least one of mobile_number or email_id must be provided.",
                                         status_code=status.HTTP_400_BAD_REQUEST)

        otp_status, otp_instance = OTP.generate_otp(mobile_number, email_id, notification_type)
        if not otp_status:
            return self.failure_response(error_code=api_response_codes.ERROR_WHILE_SAVING,
                                         message=otp_instance, status_code=status.HTTP_400_BAD_REQUEST)

        data_dict = {"mobile_number": mobile_number, "email_id": email_id, "notification_type": notification_type,
                     "otp": otp_instance.otp}

        template_status, template_data = NotificationServices(notification_type=notification_type).get_template(requested_data=data_dict)
        if not template_status:
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message=template_data, status_code=status.HTTP_400_BAD_REQUEST)

        try:
            request_id = otp_instance.request_id
            data_dict.update(template_data)

            response = NotificationServices(notification_type=notification_type).send_notification(data_dict)
            if response.get("status"):
                response["request_id"] = request_id
                return self.success_response(data=response, message="OTP sent successfully",
                                             status_code=status.HTTP_200_OK)
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message=response.get("message"), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message=str(e), status_code=status.HTTP_400_BAD_REQUEST)

    def verify_otp(self, request):
        request_args = request.data
        request_id = request_args.get("request_id")
        otp = request_args.get("otp")
        mobile_number = request_args.get("mobile_number")
        email_id = request_args.get("email_id")

        missing_params = check_mandatory_values(request_args, ["request_id", "otp"])

        if missing_params:
            return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                         message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                         data=missing_params)

        if not email_id and not mobile_number:
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message="Either Mobile Number or Email-ID is required.",
                                         status_code=status.HTTP_400_BAD_REQUEST)

        response = OTP.is_valid_otp(request_id, otp, email_id, mobile_number)

        if response["status"]:
            return self.success_response(data=response, message="OTP verified successfully",
                                         status_code=status.HTTP_200_OK)

        else:
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         message=response["message"],
                                         status_code=status.HTTP_400_BAD_REQUEST)
