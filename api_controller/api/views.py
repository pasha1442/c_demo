from api_controller.constants import PRE_PROCESS_IMAGE_BEFORE_UPLOAD
from backend.constants import API_CONTROLLER_HELP_FILE_PATH
from basics.api.views import BaseModelViewSet, AuthenticationAPIView
from django.contrib.auth import get_user_model
from basics.api import api_response_codes
from django.utils.translation import gettext_lazy as _
from api_controller.models import ApiController
from basics.utils import ImageConversion, check_mandatory_values
from chat.auth import ApiKeyAuthentication
from company.utils import CompanyUtils
from metering.utils import is_valid_metering_config
from api_controller.services.workflow_service import Workflow
from django.http import StreamingHttpResponse
import json
from basics.services.gcp_bucket_services import GCPBucketService
import newrelic.agent
import base64
import tempfile
import os
import subprocess
User = get_user_model()


class APIRouterManager(BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]

    def __init__(self):

        """
            client_session_id : is added in order to store client reference even after client_identifier is changed
        """
        self.payload_structure = {
                          "session_id": "",
                          "mobile_number": "",
                          "client_identifier": "",
                          "client_session_id": "",
                          "message": {
                            "text": "",
                            "media": {},
                            "metadata": {
                              "language": "en",
                              "timezone": "Asia/Kolkata",
                              "device_type": "",
                              "location": {
                                "lat": "",
                                "long": ""
                              },
                              "is_logged_in": False
                            }
                          }
                        }


    def manage_uploaded_media(self, payload, company, api_route='api'):
        media_payload=[]
        if "message" in payload.keys():
            media_assets = payload["message"]["media"]
            for media in media_assets:
                if media.get("type") in ["image_base64"]:
                    gcp_bucket_service = GCPBucketService()
                    media_type = "image"

                    image_data = media.get("image")

                    if PRE_PROCESS_IMAGE_BEFORE_UPLOAD:
                        image_data = self.preprocess_image(image_data)
                    image_extension = ImageConversion.get_file_extension_from_base64_string(media.get("image")) or 'jpg'
                    media_blob_name = gcp_bucket_service.get_blob_path(company=company, blob_type=media_type, blob_path=api_route, extension=image_extension)
                    uploaded_image_url = gcp_bucket_service.upload_base64_file(company, image_data, media_blob_name)
                    if uploaded_image_url:
                        media_payload.append({"type": media.get("type"), "image_url": uploaded_image_url})
            payload["message"]["media"] = media_payload
        return payload

    def preprocess_image(self, base64_image, max_file_size_mb=1, max_dimension=1024, quality=75):        
        # Extract the actual base64 data (remove data:image/jpeg;base64, if present)
        prefix = ""
        if ',' in base64_image:
            prefix = base64_image.split(',', 1)[0] + ','
            image_data = base64_image.split(',', 1)[1]
        else:
            image_data = base64_image
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpeg', delete=False) as input_file, \
                tempfile.NamedTemporaryFile(suffix='.jpeg', delete=False) as output_file:
                
                input_path = input_file.name
                output_path = output_file.name
            
            # Write the decoded image to the input file
            with open(input_path, 'wb') as f:
                f.write(base64.b64decode(image_data))
            
            # Use ffmpeg to resize and compress
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', input_path,
                '-vf', f'scale=\'min({max_dimension},iw)\':\'min({max_dimension},ih)\':force_original_aspect_ratio=decrease',
                '-q:v', str(int((100 - quality) / 5)),
                '-y',
                output_path
            ]
            
            subprocess.run(ffmpeg_cmd, capture_output=True)
            
            with open(output_path, 'rb') as f:
                processed_data = f.read()
            
            # Convert back to base64
            processed_image_data = base64.b64encode(processed_data).decode('utf-8')
            
            if prefix:
                processed_image_data = prefix + processed_image_data
            
            # Clean up temp files
            os.unlink(input_path)
            os.unlink(output_path)
            
            return processed_image_data
        
        except Exception as e:
            print(f"Image preprocessing with FFmpeg failed: {e}")
            
            # Clean up temp files if they exist
            try:
                if 'input_path' in locals() and os.path.exists(input_path):
                    os.unlink(input_path)
                if 'output_path' in locals() and os.path.exists(output_path):
                    os.unlink(output_path)
            except:
                pass
                
            return base64_image

    def refactor_payload(self, payload={}):
        _payload = self.payload_structure
        if payload:
            _payload["mobile_number"] = payload.get("mobile_number") if payload.get("mobile_number") else payload.get("mobile")
            _payload["session_id"] = payload.get("session_id")
            _payload["client_identifier"] = payload.get("client_identifier")
            _payload["client_session_id"] = payload.get("client_session_id")

            if payload.get("text"):
                _payload["message"]["text"] = payload.get("text")
            elif payload.get("message"):
                _message_text = payload["message"]["text"]
                _payload["message"]["text"] = ', '.join(_message_text) if isinstance(_message_text, list) else _message_text
            # _payload["message"]["text"] = payload.get("text") if payload.get("text") else payload["message"]["text"]
            _payload["message"]["media"] = payload["message"]["media"] if "message" in payload else {}
            _payload["message"]["metadata"] = payload["message"]["metadata"] if "message" in payload else {}
            for _key in payload.keys():
                if _key in ["api_auth_token"]:
                    _payload["message"]["metadata"][_key] = payload[_key]
            return _payload
        return payload

    def validate_required_parameters(self, api_controller, request_args):
        _required_parameters = api_controller.required_parameters
        required_params = _required_parameters if _required_parameters else ["session_id", "client_identifier",]
                                                                            #  "client_session_id"]
        missing_params = check_mandatory_values(request_args, required_params)

        return missing_params

    def execute_workflow_over_route(self, request, api_route=None):
        _args = self.refactor_payload(request.data)
        company = CompanyUtils.get_current_company_object()
        _args = self.manage_uploaded_media(_args, company, api_route)
        api_controller = ApiController.objects.filter(api_route=api_route).first()
        """ Checking Api Route"""
        if api_controller:
            try:
                company_name = company.name
                txn_name = f"{company_name}/{api_controller.api_route}"
                newrelic.agent.set_transaction_name(txn_name)
            except Exception as nr_error:
                print(f"New Relic naming error (non-critical): {nr_error}")
            """ Checking required parameters in api"""
            missing_params = self.validate_required_parameters(api_controller, _args)
            if missing_params:
                return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                             message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                             data=missing_params)
            """ Checking metering Config"""
            if is_valid_metering_config(company):
                workflow = Workflow(company=company, api_controller=api_controller, request_args=_args)
                response = StreamingHttpResponse(workflow.init_workflow(route=api_route), content_type='text/plain')
                if api_controller.workflow_stream:
                    response['Response-Type'] = 'stream-word'
                else:
                    response['Response-Type'] = 'stream-response'
                return response
                # _res = Workflow(company=company, api_controller=api_controller, request_args=_args).init_workflow(route=api_route)
                # return self.success_response(data=_res, message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
            else:
                return self.failure_response(error_code=api_response_codes.ERROR_INVALID_METERING_CONFIG,
                                             message=_(api_response_codes.MESSAGE_INVALID_METERING_CONFIG), data={})
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_URL,
                                     message=_(api_response_codes.ERROR_INVALID_URL),
                                     data={"company": company.name if company else "",
                                           "api_route": api_route,
                                           "token": request.META.get('HTTP_AUTHORIZATION', ' ')})


class APIControllerManager(AuthenticationAPIView, BaseModelViewSet):

    def get_available_routes(self, request):
        request_args = request.data
        missing_params = check_mandatory_values(request_args, ["company_id"])
        if missing_params:
            return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                         message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                         data=missing_params)
        company_id = request_args.get("company_id")
        routes = ApiController.without_company_objects.filter(company_id=company_id).values("id", "name",
                                                                                            "base_api_url", "api_route")
        return self.success_response(data=routes,
                                     message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)

        return self.failure_response(error_code=api_response_codes.ERROR_WHILE_SAVING,
                                     message=_(api_response_codes.ERROR_WHILE_SAVING),
                                     data={})

    def update_graph_json(self, request):
        request_args = request.data
        missing_params = check_mandatory_values(request_args, ["route_id", "graph_json"])
        if missing_params:
            return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                         message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                         data=missing_params)
        route_id = request_args.get("route_id")
        graph_json = request_args.get("graph_json")
        api_controller = ApiController.objects.filter(id=route_id).first()
        if api_controller:
            api_controller.graph_json = json.loads(graph_json)
            api_controller.save()
            return self.success_response(data={},
                                         message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        else:
            return self.failure_response(error_code=api_response_codes.ERROR_API_ROUTE_NOT_FOUND,
                                         message=_(api_response_codes.MESSAGE_API_ROUTE_NOT_FOUND),
                                         data={"route_id": route_id})

    def get_graph_json_over_route(self, request):
        request_args = request.data
        missing_params = check_mandatory_values(request_args, ["route_id"])

        if missing_params:
            return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                         message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                         data=missing_params)
        route_id = request_args.get("route_id")
        api_controller = ApiController.objects.filter(id=route_id).first()
        if api_controller:
            return self.success_response(data={
                "route_id": route_id,
                "graph_json": api_controller.graph_json
            },
                message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        else:
            return self.failure_response(error_code=api_response_codes.ERROR_API_ROUTE_NOT_FOUND,
                                         message=_(api_response_codes.MESSAGE_API_ROUTE_NOT_FOUND),
                                         data={"route_id": route_id})

    def get_help_window_content(self, request):
        result = {}
        try:
            with open(API_CONTROLLER_HELP_FILE_PATH, 'r') as file:
                content = file.read()
            return self.success_response(data={"sidebar_content": content, "heading": "Help"},
                                         message="Data fetch successfully")
        except FileNotFoundError:
            return self.failure_response(error_code=api_response_codes.ERROR_DATA_NOT_FOUND,
                                         message=_(api_response_codes.MESSAGE_DATA_NOT_FOUND))

        
        
class ExternalAPIControllerManager(BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]
    
    def get_company_wise_voice_assistant_workflows(self, request):
        
        try:
            voice_assistant_api_controllers = ApiController.without_company_objects.exclude(voice_assistant_method='')
            
            response = {}
            for api_controller in voice_assistant_api_controllers:
                if not response.get(api_controller.company_id):
                    response[api_controller.company_id] = {'company_name': api_controller.company.name, 'api_controller_routes': [], 'company_number': ''}
                
                if api_controller.phone_number:
                    response[api_controller.company_id]['company_number'] = api_controller.phone_number
                    
                entry = {"name": api_controller.name, "api_route": api_controller.api_route, "api_controller_phone_number":api_controller.phone_number}
                response[api_controller.company_id]['api_controller_routes'].append(entry)
                
            
            
            return self.success_response(data=response,
                                         message="Data fetch successfully")
        except FileNotFoundError:
            return self.failure_response(error_code=api_response_codes.ERROR_DATA_NOT_FOUND,
                                         message=_(api_response_codes.MESSAGE_DATA_NOT_FOUND))