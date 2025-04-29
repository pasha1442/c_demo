from django.apps import apps
import requests
from services.response_processor import BaseResponseProcessor

Service = apps.get_model('services', 'Service')
APIEndpoint = apps.get_model('services', 'APIEndpoint')



class ServiceProcessor:

    def process_scheduled_apis(self):
        services = Service.objects.filter(is_active=True)
        if services:
            self.process_api_calls(services)

    def process_api_calls(self, services):
        api_calls = APIEndpoint.objects.filter(service__in=services,
                                               is_active=True,
                                               endpoint_type__in=[APIEndpoint.ENDPOINT_TYPE_GET_API,
                                                                  APIEndpoint.ENDPOINT_TYPE_POST_API])
        for api_call in api_calls:
            self.process_api_call(api_call=api_call)

    def process_api_call(self, api_call):
        print(f"API Processing: #{api_call.id}", api_call.name)
        _url = api_call.endpoint_url
        _token = api_call.endpoint_token
        _api_method = api_call.endpoint_type
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {api_call.endpoint_token}"
        }
        if _url and _token and _api_method:
            if _api_method == APIEndpoint.ENDPOINT_TYPE_GET_API:
                _res = requests.get(url=_url, headers=headers, params={})
                data = _res.json()
                if data:
                    BaseResponseProcessor().call_corresponding_response_processor(api_call.postprocessor, data)
                    print("Data Processed Successfully")
        else:
            print("Error: Incomplete Arguments")
