from django.urls import path
from auth.api.views import UserApiView, UserAuthenticationManager

urlpatterns = [
    path('user/set-current-company', UserApiView.as_view({"post": "set_current_company"})),
    path('user/get-user-wise-company-choices', UserApiView.as_view({"get": "get_user_wise_company_choices"})),
    path('user/send-otp', UserAuthenticationManager.as_view({"post": "send_otp"}), name="send_otp"),
    path('user/verify-otp', UserAuthenticationManager.as_view({"post": "verify_otp"}), name="verify_otp"),


]