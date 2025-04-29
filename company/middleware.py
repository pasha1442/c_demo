from django.http import HttpResponse, HttpResponseForbidden
from basics.middleware import BaseMiddleware
from company.admin import company_admin_site
from company.models import Company
from rest_framework_simplejwt.authentication import JWTAuthentication
from company.utils import CompanyUtils
from dash.models import ApiKey


class CompanySessionMiddleware(BaseMiddleware):

    def process_request(self, request):
        
        if request.path.startswith('/api/login/'):
            return
        
        view_name = request.get_full_path()
        # user must be authenticated for non api requests
        if not request.user.is_authenticated and '/api/' not in request.get_full_path():
            return
        # only superuser should be able to access admin panel
        # if '/admin/' in view_name and not request.user.is_superuser:
        #     return redirect(reverse('company_admin_site:index'))
        if '/api/chat/wawebhook' in view_name or '/api/chat/dynamic-workflow-webhook/' or "/chat/voice-assistant" in view_name:
            return
        elif '/api/' in view_name:
            return self.set_company_for_api(self, request)
        # we are considering all non api and non admin requests as company dashboard requests
        # therefore company specific sessions must be set for current user
        elif '/admin/' not in view_name:
            return self.set_company_for_admin(self, request)

    @staticmethod
    def set_company_for_admin(self, request):
        if request.user.is_superuser:
            if 'company' in request.session:
                session_company = request.session['company']
                company = Company.objects.filter(is_active=True, id=session_company).first()
            else:
                company = Company.objects.filter(is_active=True).first()

        else:
            pass
            # company = request.user.company
            # if company and not company.is_active:
            #     return HttpResponseForbidden()

        # if not company:
        #     return HttpResponseForbidden()

        # Set user company...
        # company_admin_site.set_company(company)

    @staticmethod
    def set_company_for_api(self, request):
        view_name = request.get_full_path()
        if request.user.is_authenticated:
            # question?
            # why is it setting company for admin?
            self.set_company_for_admin(self, request)
        else:
            if 'api/' in view_name:
                return CompanySessionMiddleware.authenticate_api_key(request)
            else:
                auth = JWTAuthentication()
                header = auth.get_header(request)
                if header is None:
                    return

                raw_token = None
                try:
                    if 'api/login/' not in view_name:
                        raw_token = auth.get_raw_token(header)
                        raw_token = auth.get_validated_token(raw_token) # type: ignore
                        if 'sso_session_id' in raw_token and raw_token['sso_session_id']:
                            sso_session_id = raw_token['sso_session_id']
                            status = SSOSync.middleware_sso_session_id_validation(sso_session_id) # type: ignore
                            if not status:
                                return HttpResponseForbidden()
                    user, a = auth.authenticate(request) # type: ignore
                except Exception as e:
                    return

                company = None
                if user is not None:
                    company = user.company
                # if raw_token:
                #     token_company_id = None
                #     if 'api/user-auth-detail/' in view_name and (user.is_superuser or user.company_supervisor) and 'superuser_company_choice' in request.GET and request.GET.get('superuser_company_choice', None):
                #         token_company_id = request.GET.get('superuser_company_choice', None)
                #     elif 'company_id' in raw_token and raw_token['company_id']:
                #         token_company_id = raw_token['company_id']
                #     if user and (user.is_superuser or user.company_supervisor) and token_company_id:
                #         company = Company.objects.filter(is_active=True).annotate(
                #             id_md5=MD5(Cast('id', output_field=CharField()))
                #         ).filter(id_md5=token_company_id, companysettings__isnull=False).first()

                #     if user.company_supervisor and company not in user.companies.all():
                #         company = None

                if user is None or company is None:
                    return HttpResponseForbidden()
                elif not company.is_active:
                    return HttpResponseForbidden()
                else:
                    # request.session['timezone'] = self.__set_timezone(company)
                    # # Set user location...
                    # self.__set_location_api(request, company, user)
                    # # Set company settings...
                    # self.__set_company_settings(company)
                    # active_company = get_object_or_404(Company, pk=company)
                    company_admin_site.set_company(company)
                    request.session['company'] = company.id

    @staticmethod
    def authenticate_api_key(request):
        if request.method == "GET":
            return None
        api_key = request.META.get('HTTP_AUTHORIZATION')
        if not api_key:
            return HttpResponse('Unauthorized', status=401)
        api_key = api_key.replace('Bearer ', '', 1)

        try:
            # Use the custom manager that bypasses the company filter
            key = ApiKey.without_company_objects.get(key=api_key)
        except ApiKey.DoesNotExist:
            return HttpResponse('Unauthorized', status=401)
        
        company = key.company
        CompanyUtils.set_company_registry(company=company)
        request.session['company'] = company.id
        return None