from django.http import HttpResponse
from rest_framework.authentication import BaseAuthentication
from company.utils import CompanyUtils
from dash.models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):

    def authenticate(self, request):
        api_key = request.META.get('HTTP_AUTHORIZATION')
        
        if request.method == "GET" and not api_key:
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
        return (key.company_id, None)
