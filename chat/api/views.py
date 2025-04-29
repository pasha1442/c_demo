import json

from api_controller.models import ApiController
from backend.constants import CURRENT_API_COMPANY
from backend.services.kafka_service import BaseKafkaService
from basics.api.views import BaseModelViewSet, AuthenticationAPIView
from django.contrib.auth import get_user_model
from basics.utils import Registry, check_mandatory_values
from basics.api import api_response_codes
from django.utils.translation import gettext_lazy as _
from chat.dynamichooks.dynamic_hook import DynamicHook
from chat.services.agent_runner import AgentRunner
from chat.services.conversation_manager_service import ConversationManagerService
from chat.services.workflow_attribute_manager.workflow_attribute_service import WorkflowAttributeService
from chat.states.dynamic_hook_state import DynamicHookState
import chat.utils as utils
from chat.factory import get_client_class
from company.utils import CompanyUtils
from metering.services.openmeter import OpenMeter
from chat.demo.voice_assistant.utils import start_twilio_stream
from decouple import config
from twilio.rest import Client
from django.http import HttpResponse, JsonResponse
from chat.models import Prompt, Conversations, ConversationSession, WorkflowAttributes
from django.db.models import OuterRef, Subquery
from rest_framework.decorators import api_view, permission_classes
from chat.auth import ApiKeyAuthentication
from asgiref.sync import async_to_sync
from backend.services.cache_service import CacheService
import time
from datetime import timedelta
from django.utils import timezone
from django.db.models import Max


User = get_user_model()


class ChatBot(AuthenticationAPIView, BaseModelViewSet):

    def send_message(self, request):
        request_data = request.data
        user_id = request.user.id
        company_id = request_data.get('company_id', None)
        agent = request.data.get('agent', None)
        _message = request_data.get('message', None)
        session_id = request.data.get('session_id')
        client_session_ref_id = request.data.get('client_session_ref_id')
        extra_save_data = {}
        _required_values = check_mandatory_values(request_data, ['company_id', 'message'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        print("send_message API", user_id, company_id)

        if session_id:
            extra_save_data['session_id'] = session_id
        if client_session_ref_id:
            extra_save_data['client_session_ref_id'] = client_session_ref_id
        if agent:
            utils.save_conversation(request.user, 'user', "0000", _message, extra_save_data)
            company = request.user.current_company
            company_name = company.name
            company_class = get_client_class(company_name)

            version = request.query_params.get('version', '1.0')
            company_class_response = company_class.process_request(request, _message, "0000", version)
            print(company_class_response)
            return self.success_response(data={"message": company_class_response.get('message', '')},
                                         message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        if _message:
            ai_response = AgentRunner().initiate_request(user=request.user, message=_message,
                                                         extra_save_data=extra_save_data)
        return self.success_response(data={"message": ai_response},
                                     message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        # return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
        #                              message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})


class PromptManager(AuthenticationAPIView, BaseModelViewSet):

    def get_active_prompts(self, request):
        if request.user and request.user.current_company:
            prompts = Prompt.objects.filter(company=request.user.current_company)
            res_prompts = [{"key": prompt.prompt_type, "val": prompt.get_prompt_type_display()} for prompt in prompts]
            return self.success_response(data=res_prompts,
                                         message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})


class VoiceAssistantManager(BaseModelViewSet):

    def process_user_call(self, request):
        agent_phone_number = request.POST.get("To")
        customer_phone_number = request.POST.get("From")

        company = CompanyUtils.get_company_from_phone_number(agent_phone_number)
        api_controller = ApiController.objects.filter(api_route="initiate-call", company=company).first()
        openmeter_obj = OpenMeter(company=company, api_controller=api_controller,
                                  request_args={"session_id": customer_phone_number})
        session_id = openmeter_obj.billing_session_id

        response = start_twilio_stream(request, session_id)
        return HttpResponse(str(response), content_type="application/xml")

    def get_call_status(self, request):
        try:
            call_sid = request.GET.get('call_sid')
            account_sid = config("TWILIO_ACCOUNT_SID")
            auth_token = config('TWILIO_AUTH_TOKEN')
            client = Client(account_sid, auth_token)
            call = client.calls(call_sid).fetch()

            response = {"call_status": call.status}
            return JsonResponse(response, status=200)
        except Exception as e:
            print(f"Error occurred: {e}")
            response = {"error": f"Error occured: {e}"}
            return JsonResponse(response, status=500)

    def voice_call_status_callback(self, request):
        call_status = request.POST.get('CallStatus')
        user_phone_number = request.POST.get('To')[3:]
        company_id = request.GET.get('company_id')
        api_route = request.GET.get('workflow')
        client_session_id = request.POST.get('CallSid')

        company = CompanyUtils.get_company_from_company_id(company_id)
        Registry().set(CURRENT_API_COMPANY, company)

        if call_status == "completed":
            session_ids = ConversationSession.objects.filter(client_session_id=client_session_id,
                                                             company_id=company_id).values_list("session_id", flat=True)

            for session_id in session_ids:
                dynamic_hook_state = DynamicHookState(session_id=session_id, client_identifier=user_phone_number,
                                                      api_route=api_route, hook_type='summary_generation',
                                                      company_id=company_id)
                DynamicHook(state=dynamic_hook_state.to_dict()).publish()

            return JsonResponse({'success': "summary generated successfully"}, status=200)

        return JsonResponse({"error": "couldn't generate summary"}, status=200)


class InternalConversationManager(AuthenticationAPIView, BaseModelViewSet):

    def get_conversation_over_client_identifier(self, request):

        client_ref_id = request.data.get('client_ref_id')
        request_data = request.data
        _required_values = check_mandatory_values(request_data, ['client_ref_id'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        if client_ref_id:
            conversations = Conversations.objects.filter(session_id=client_ref_id,
                                                         role__in=["user", "assistant"]).values("id", "role",
                                                                                                "session_id", "message",
                                                                                                "message_type",
                                                                                                "message_metadata",
                                                                                                "created_at")

            return self.success_response(data=conversations,
                                         message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})

    def get_all_recent_sessions_list(self, request):

        request_data = request.data
        _required_values = check_mandatory_values(request_data, [])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA,
                message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        client_identifier = request_data.get("client_identifier", None)
        if client_identifier:
            recent_sessions = (
                ConversationSession.objects.filter(client_identifier=client_identifier).order_by('-created_at').values_list(
                    'session_id', flat=True)[:20]
                )
        else:
            recent_sessions = ConversationSession.objects.filter(
                    created_at__gte=timezone.now() - timedelta(hours=48)
                ).values('session_id').annotate(
                    latest_created_at=Max('created_at')
                ).order_by('-latest_created_at').values_list('session_id', flat=True)[:20]

            # latest_sessions = (
            #     Conversations.objects
            #         .filter(role__in=["user", "assistant"], client_identifier=client_identifier,
            #                 session_id=OuterRef('session_id'))
            #         .order_by('-created_at')
            #         .values('id')[:1]
            # )
            # latest_sessions = (
            #     ConversationSession.objects
            #         .filter(role__in=["user", "assistant"], client_identifier=client_identifier,
            #                 session_id=OuterRef('session_id'))
            #         .order_by('-created_at')
            #         .values('id')[:1]
            # )
        # else:
        #     latest_sessions = (
        #         ConversationSession.objects
        #             .filter(role__in=["user", "assistant"], session_id=OuterRef('session_id'))
        #             .order_by('-created_at')
        #             .values('id')[:1]
        #   )
            # latest_sessions = (
            #     ConversationSession.objects
            #         .filter(role__in=["user", "assistant"], session_id=OuterRef('session_id'))
            #         .order_by('-created_at')
            #         .values('id')[:1]
            # )

        # recent_sessions = (
        #     Conversations.objects.filter(id__in=Subquery(latest_sessions)).order_by('-created_at').values_list(
        #         'session_id', flat=True)[:20]
        # )
        return self.success_response(data=recent_sessions,
                                     message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})
        
    def save_workflow_attribute(self, request):
        workflow_attribute = json.loads(request.data["savedResponseFormatter"])
        
        _required_values = check_mandatory_values(workflow_attribute, ['name', 'attribute_type', 'content'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA,
                message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
            
        name = workflow_attribute['name']
        attribute_type = workflow_attribute['attribute_type']
        content = workflow_attribute['content']
        response_formatter_type = workflow_attribute.get('response_formatter_type', None)
        
        workflow_attribute_service = WorkflowAttributeService()
        workflow_attribute_service.save_workflow_attribute(name, attribute_type, content, response_formatter_type)
        return self.success_response(data={}, message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        
    def get_workflow_attribute(self, request):
        # Get the 'attribute_type' parameter from the request
        attribute_type = request.GET.get('attribute_type', None)

        if attribute_type is None:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA,
                message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=['attribute_type']
            )
        
        formatters = WorkflowAttributeService().get_workflow_attributes(attribute_type)
        
        return self.success_response(data=formatters, message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)


class ExternalConversationManager(AuthenticationAPIView, BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = []

    def get_conversation_over_client_identifier(self, request):

        client_ref_id = request.data.get('client_ref_id')
        request_data = request.data
        _required_values = check_mandatory_values(request_data, ['client_ref_id'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        if client_ref_id:
            conversations = Conversations.objects.filter(session_id=client_ref_id,
                                                         role__in=["user", "assistant"]).values("id", "role",
                                                                                                "session_id", "message",
                                                                                                "message_type",
                                                                                                "message_metadata",
                                                                                                "created_at")

            return self.success_response(data=conversations,
                                         message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})

    def get_recent_sessions_list(self, request):

        request_data = request.data
        _required_values = check_mandatory_values(request_data, ["client_identifier"])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        client_identifier = request_data.get("client_identifier", None)

        recent_sessions = []
        if client_identifier:
            recent_sessions = (ConversationSession.objects.filter(client_identifier=client_identifier).order_by(
                '-created_at').values_list('session_id', 'created_at'))

        return self.success_response(data=recent_sessions,
                                     message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})

    def get_summary_over_session_id(self, request):

        session_id = request.data.get('session_id')
        client_session_id = request.data.get('client_session_id')
        if session_id:
            conv_manager = ConversationManagerService()
            summaries = conv_manager.fetch_summary_over_session_id(session_id)

            return self.success_response(data=summaries, message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        
        elif client_session_id:
            conv_manager = ConversationManagerService()
            summaries = conv_manager.fetch_summary_over_client_session_id(client_session_id)

            return self.success_response(data=summaries, message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})
        

    def update_client_identifier_over_client_session_id(self, request):

        client_identifier = request.data.get('client_identifier')
        client_session_id = request.data.get('client_session_id')
        request_data = request.data
        _required_values = check_mandatory_values(request_data, ['client_identifier', 'client_session_id'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        if client_identifier and client_session_id:
            conv_manager = ConversationManagerService()
            _result = conv_manager.update_client_identifier_over_client_session_id(client_identifier, client_session_id)
            if _result:
                return self.success_response(data={},
                                             message=api_response_codes.MESSAGE_UPDATED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})


class WorkflowStatusManager(AuthenticationAPIView, BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = []

    def get_workflow_status_over_request_id(self, request):
        request_id = request.data.get('request_id', "")
        request_data = request.data
        _required_values = check_mandatory_values(request_data, ['request_id'])
        if _required_values:
            return self.failure_response(
                error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                data=_required_values
            )
        if request_id:
            cache = CacheService(CacheService.CACHE_DB_WORKFLOW_STATUS_CACHE)
            status = cache.get(request_id)
            return self.success_response(data=status,
                                         message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})

    def verify_workflow_status_as_completed_over_request_id(self, request):
        try:
            time.sleep(55)
            request_id = request.data.get('request_id', "")
            request_data = request.data
            _required_values = check_mandatory_values(request_data, ['request_id'])
            if _required_values:
                return self.failure_response(
                    error_code=api_response_codes.ERROR_INVALID_DATA, message=_(api_response_codes.MESSAGE_INVALID_DATA),
                    data=_required_values
                )
            if request_id:
                cache = CacheService(CacheService.CACHE_DB_WORKFLOW_STATUS_CACHE)
                status = cache.get(request_id)
                if status.get("status") == "Completed":
                    return self.success_response(data=status,
                                             message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})
        except Exception as e:
            print("Error:", str(e))
