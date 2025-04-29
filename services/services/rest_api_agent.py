from django.apps import apps
import requests
from company.utils import CompanyUtils
from services.response_processor import BaseResponseProcessor
from company.utils import CompanyUtils
Service = apps.get_model('services', 'Service')
APIEndpoint = apps.get_model('services', 'APIEndpoint')


class RestAPIAgent:

    def invoke_agent(self, slug, args={}, ai_args={}, custom_headers={}, company=None):
        if company:
            CompanyUtils.set_company_registry(company)
        _api = APIEndpoint.objects.filter(slug=slug, is_active=True).first()
        if not _api:
            print("* No API call found", "Slug:", slug)
            return
        return self.invoke_http_request(_api, args, ai_args, custom_headers)

    def invoke_http_request(self, api_call, args={}, ai_args={}, custom_headers={}):
        print(f"API Processing: #{api_call.id}", api_call.name)
        _url = api_call.endpoint_url
        _token = api_call.endpoint_token if api_call.endpoint_token else args.get('token')
        _api_method = api_call.endpoint_type or args.get('method', 'GET')
        _body = api_call.request_payload
        _params = self.build_req_body(api_call.mapping_payload, _body, args, ai_args)
        
        # For Authorization: The complete authorization header (e.g., 'Bearer <token>') 
        # should be stored in the 'endpoint token' field of the service endpoint. 
        # This allows flexibility for different auth schemes (Bearer, Basic, etc.).
        headers = {}
        if custom_headers:
            headers = custom_headers
        elif api_call.endpoint_headers:
            headers = api_call.endpoint_headers
        elif _token:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': _token,
            }
        if _url and _api_method:
            _res = None
            if _api_method == APIEndpoint.ENDPOINT_TYPE_GET_API:
                _res = requests.get(url=_url, headers=headers, params=_params)
            elif _api_method == APIEndpoint.ENDPOINT_TYPE_POST_API:
                if 'file' in _params:
                    headers = {
                        'Authorization': f"{_token}" if _token else "" 
                    }
                    payload = {}
                    _res = requests.post(url=_url, headers=headers, data=payload,files=_params)
                else:
                    _res = requests.post(url=_url, headers=headers, json=_params)

            if _res:
                data = _res.json()
                if api_call.postprocessor:
                    data = BaseResponseProcessor().call_corresponding_response_processor(
                        api_call.postprocessor,
                        data)
                return data
        else:
            print("Error: Incomplete Arguments")

    def build_req_body(self, mapping_json, body, args, ai_args={}):
        if args:
            for key in body:
                if args.get(key, None):
                    body[key] = args[key]
        if ai_args:
            for key in body:
                if ai_args.get(key, None):
                    body[key] = ai_args[key]
        if mapping_json:
            for ai_arg_key in ai_args:
                if mapping_json.get(ai_arg_key, None):
                    _map_key = mapping_json.get(key)
                    body[_map_key] = ai_args[ai_arg_key]
        # print("body", body)
        # todo: also store datatype in json payload
        return body
