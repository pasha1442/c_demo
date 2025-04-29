from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from company.admin import company_admin_site
from django.shortcuts import get_object_or_404
from company.models import CompanyUser


# class ApiKeyBackend(BaseBackend):
#     def authenticate(self, request, email=None, password=None):
#         UserModel = get_user_model()
#         try:
#             user = UserModel.objects.get(email=email)
#         except UserModel.DoesNotExist:
#             return None
#         user = get_object_or_404(CompanyUser, pk=user_id)
#         company = user.company
#         print("hekko how are you")

#         if user.check_password(password):
#             print(user)
#             # breakpoint()
#             company_admin_site.set_company(user)
#             # request.session['company'] = user
#             return user
#         return None