from decimal import Decimal
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from api_controller.models import ApiController
from backend.constants import CURRENT_API_COMPANY
from backend.custom_permissions import CustomPagesPermissionManager
from basics.api.views import BaseAsyncAPIView
from basics.utils import Registry
from chat.auth import ApiKeyAuthentication
import chat.utils as utils
from company.models import Company
from metering.services.openmeter import OpenMeter
from metering.services.session_service import SessionManager
from .factory import get_client_class, get_client_flow_json
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes
from rest_framework import status
from django.views.generic import TemplateView
from django.contrib.admin import site
from django.utils.decorators import method_decorator
import chat.graph_workflow as graph_workflow
from langfuse.decorators import langfuse_context
from chat import factory
from asgiref.sync import sync_to_async
from decouple import config
from django.core.exceptions import PermissionDenied


class ChatAPIView(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        text = request.data.get('text')
        mobile = request.data.get('mobile')
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')
        if not text:
            return Response({'error': 'No text provided'}, status=400)
        if not mobile:
            return Response({'error': 'Please provide customer mobile number'}, status=400)
        if not session_id:
            return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        extra_save_data = {}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier

        utils.save_conversation(request.user, 'user', mobile, text, extra_save_data)
        company = Company.objects.get(id=request.user)
        company_name = company.name
        company_class = get_client_class(company_name)

        version = request.query_params.get('version', '1.0')

        company_class_response = company_class.process_request(request, text, mobile, version)
        if version == '2.0':
            try:
                json_string = str(company_class_response['message'])
                data = utils.extract_json_from_string(json_string)
                # def clean_json(data):
                #     if isinstance(data, dict):
                #         return {
                #             key: clean_json(value)
                #             for key, value in data.items()
                #             if value is not None and clean_json(value) != {}
                #         }
                #     elif isinstance(data, list):
                #         return [clean_json(item) for item in data if clean_json(item) != {}]
                #     else:
                #         return data
                # data = clean_json(data)
                return JsonResponse(data)
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                static_data = """
                    {"output":{"PlanRecommendation":"Waiting for more information before providing recommendations","action":{"Other":{"Reason":"Ask for more information to narrow down recommendations"}}}}
                """
                data = json.loads(static_data)
                return JsonResponse(data)

        return Response({'message': company_class_response})


class AgentChatAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        text = request.data.get('text')
        mobile = request.data.get('mobile')
        conversation = request.data.get('conversation')
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')

        if not mobile:
            return Response({'error': 'Please provide customer mobile number'}, status=400)
        if not text:
            return Response({'error': 'No text provided'}, status=400)

        # utils.save_conversation(request.user,'user',mobile,text)
        extra_save_data = {}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier
        utils.save_conversation(request.user, 'user', mobile, text, extra_save_data)
        company = Company.objects.get(id=request.user)
        company_name = company.name

        company_class = get_client_class(company_name)
        company_class_response = company_class.agent_request(request, text, conversation, mobile)
        return Response({'message': company_class_response})


class AgentProfileAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        agent_reference_id = request.data.get('agent_reference_id')
        duration = request.data.get('duration')
        if not agent_reference_id:
            return Response({'error': 'Please provide agent reference id'}, status=400)

        company = Company.objects.get(id=request.user)
        company_name = company.name

        company_class = get_client_class(company_name)
        evaluate = company_class.evaluate_agent_request(request, agent_reference_id, duration)
        return Response({'data': evaluate})

    def get(self, request, format=None):
        agent_reference_id = request.query_params.get('agent_reference_id')
        if not agent_reference_id:
            return Response({'error': 'Please provide agent reference id'}, status=400)

        agent_data = utils.get_agent_data(agent_reference_id)
        return Response({'data': agent_data})


class SummaryChatAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        mobile = request.data.get('mobile')
        conversation = request.data.get('conversation')
        session_id = request.data.get('session_id')

        if not conversation:
            return Response({'error': 'No conversation provided'}, status=400)

        if not session_id:
            return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        company = Company.objects.get(id=request.user)
        company_name = company.name
        company_class = get_client_class(company_name)
        company_class_response = company_class.summary_request(request, conversation, mobile)

        return Response({'message': company_class_response})


class ActionChatAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        mobile = request.data.get('mobile')
        conversation = request.data.get('conversation')
        session_id = request.data.get('session_id')

        if not conversation:
            return Response({'error': 'No conversation provided'}, status=400)
        if not session_id:
            return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        company = Company.objects.get(id=request.user)
        company_name = company.name
        company_class = get_client_class(company_name)
        company_class_response = company_class.actionables_request(request, conversation, mobile)

        return Response({'message': company_class_response})


class SenAnalysisChatAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        mobile = request.data.get('mobile')
        conversation = request.data.get('conversation')
        session_id = request.data.get('session_id')

        if not conversation:
            return Response({'error': 'No conversation provided'}, status=400)
        if not session_id:
            return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        company = Company.objects.get(id=request.user)
        company_name = company.name

        company_class = get_client_class(company_name)
        company_class_response = company_class.sen_analysis_request(request, conversation, mobile)
        return Response({'message': company_class_response})


class ProfileUpdateChatAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        mobile = request.data.get('mobile')
        conversation = request.data.get('conversation')
        if not conversation:
            return Response({'error': 'No conversation provided'}, status=400)
        if not mobile:
            return Response({'error': 'Please provide customer mobile number'}, status=400)

        company = Company.objects.get(id=request.user)
        company_name = company.name
        company_class = get_client_class(company_name)
        company_class_response = company_class.profile_update_request(request, conversation, mobile)
        return Response({'data': company_class_response})

    def get(self, request, format=None):
        # mobile = request.data.get('mobile')
        # country codes?
        mobile = request.query_params.get('mobile')
        if not mobile:
            return Response({'error': 'Please provide customer mobile number'}, status=400)

        pd = utils.get_customer_profile_temp(mobile)
        return Response({'data': pd})

    def put(self, request, format=None):
        mobile = request.data.get('mobile')
        profile_data = request.data.get('profile_data')

        if not mobile:
            return Response({'error': 'Please provide customer mobile number'}, status=400)
        if not profile_data:
            return Response({'error': 'Please provide profile_data to update'}, status=400)

        company = Company.objects.get(id=request.user)
        company_name = company.name

        company_class = get_client_class(company_name)
        company_class_response = company_class.profile_update_request_manual(profile_data, mobile)
        return Response({"status": company_class_response}, status=status.HTTP_200_OK)


class ConversationHistoryAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def get(self, request, format=None):
        mobile = request.query_params.get('mobile')
        if not mobile:
            return Response({'error': 'Please provide customer mobile number'}, status=400)

        pd = utils.fetch_session_history(mobile)
        return Response({'data': pd})


def index(request):
    return render(request, 'index.html')


def search_page(request):
    return render(request, 'search.html')


def geeta_chat_page(request):
    return render(request, 'geeta_chat.html')


class GeetaSearchAPIVIew(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def get(self, request, format=None):
        shloka_no = request.query_params.get('shloka_no')
        if not shloka_no:
            return Response({'error': 'Please provide shloka no'}, status=400)

        shloka_no = f'Bg. {shloka_no}'
        shloka = utils.fetch_shloka_from_geeta(shloka_no)
        return Response({'data': shloka})


def index(request):
    return render(request, 'index.html')


def gvi_search_page(request, chapter_no=None):
    if chapter_no is None:
        return redirect(reverse('gvi_home_page'))
    else:
        chapter_decimal = Decimal(chapter_no)
        api_view = GeetaSearchAPIVIew()
        mock_request = type('MockRequest', (), {
            'query_params': {'shloka_no': str(chapter_decimal)},
            'headers': {'Authorization': 'kl-9544ea96-b1af-4446-9cef-cdde602733a3'},
            'META': {'HTTP_AUTHORIZATION': 'kl-9544ea96-b1af-4446-9cef-cdde602733a3'}
        })()
        api_response = api_view.get(mock_request)
        search_data = api_response.data if hasattr(api_response, 'data') else api_response
        key_mapper = {
            'chapter_no': 'Chapter',
            'in_english_spelling': None,
            'in_sanskrit': None,
            'shloka_no': None,
            'purport': 'Purport',
            'translation': 'Translation',
            'url': 'Source'
        }
        ordered_keys = ['chapter_no', 'in_sanskrit', 'in_english_spelling', 'shloka_no', 'translation', 'purport',
                        'url']
        ordered_data = {key: search_data['data'].get(key) for key in ordered_keys}  # type: ignore

        context = {
            'search_results': ordered_data,
            'key_mapper': key_mapper,
        }
        return render(request, 'gvi/search.html', context)


def gvi_chat_page(request):
    return render_chat_page(request, 'gvi/chat.html')


def auriga_chat_page(request):
    return render_chat_page(request, 'cygnusalpha/auriga-chat.html')


def stitch_chat_page(request):
    return render_chat_page(request, 'stitch/chat.html')


def recobee_chat_page(request):
    return render_chat_page(request, 'recobee/chat.html')


def kindlife_chat_page(request):
    return render_chat_page(request, 'kindlife/chat.html')


def kindlife_bizz_chat_page(request):
    return render_chat_page(request, 'kindlife/kindlife_bizz_chat.html')


def gvi_home_page(request):
    return render_chat_page(request, 'gvi/home_page.html')


def omf_contact_us_page(request):
    return render_chat_page(request, 'omf/contact_us.html')


def recobee_api_chat_page(request):
    return render_chat_page(request, 'recobee/recobee_api_chat.html')


def recobee_multimodel_chat_page(request):
    return render_chat_page(request, 'recobee/multimodeltest_.html')


def render_chat_page(request, template_name=''):
    has_page_access = CustomPagesPermissionManager().get_backend_custom_page_permissions(request)
    if has_page_access:
        return render(request, template_name)
    return render(request, 'error/403.html')


@api_view(['POST'])
@authentication_classes([ApiKeyAuthentication])
def chatbot_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        text = data.get('message')
        mobile = '9816640889'  # to be changed
        utils.save_conversation(request.user, 'user', mobile, text)
        # request.user
        company = Company.objects.get(id=request.user)
        company_name = company.name
        company_class = get_client_class(company_name)
        company_class_response = company_class.process_request(request, text, mobile)
        return JsonResponse({'reply': company_class_response['message']})
    return JsonResponse({'error': 'Invalid request'}, status=400)


class ChatView(TemplateView):
    template_name = 'chat_template.html'

    def get_context_dataq(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add additional context
        context['name'] = 'Django'
        return context

    def get_context_data(self, **kwargs):
        return dict(
            site.each_context(self.request),
        )


class ConversationHistory(TemplateView):
    template_name = 'admin/chat/conversations/conversation_history.html'

    def get_context_dataq(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add additional context
        context['name'] = 'Django'
        return context

    def get_context_data(self, **kwargs):
        if not self.request.user.has_perm('custom_auth.can_view_conversation_history'):
            raise PermissionDenied  # Raise 403 error if the user lacks permission
        return dict(
            site.each_context(self.request),
        )


class GviGraphView(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        text = request.data.get('text')
        mobile = request.data.get('mobile')
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')
        if not text:
            return Response({'error': 'No text provided'}, status=400)
        if not mobile:
            return Response({'error': 'Please provide customer mobile number, param mobile missing'}, status=400)
        if not session_id:
            return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        extra_save_data = {}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier

        company = Company.objects.get(id=request.user)
        company_name = company.name
        response = run_workflow_for_client(company_name=company_name, default_llm="gpt-4o", tool_file="tools.py")
        indexed_response = {str(i): message for i, message in enumerate(response)}
        for i, message in enumerate(response):
            print(f"Part {i}: {message}")

        return JsonResponse({'messages': indexed_response})
        # return Response({'message': response})


def run_workflow_for_client(company_name: str, default_llm, tool_file: str, max_tool_calls: int = 3):
    try:
        client_json = get_client_flow_json(company_name)
        # ???
        # Import entire file or only the required function
        # ???
        result = graph_workflow.run_workflow(client_json, default_llm, tool_file, max_tool_calls)
        return result
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")


class QdegreeGraphView(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        company = Company.objects.get(id=request.user)
        langfuse_context.configure(
            secret_key=company.langfuse_secret_key,
            public_key=company.langfuse_public_key
        )

        text = request.data.get('text')
        mobile = request.data.get('mobile')
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')
        if not text:
            return Response({'error': 'No text provided'}, status=400)
        if not mobile:
            return Response({'error': 'Please provide customer mobile number, param mobile missing'}, status=400)
        # if not session_id:
        #     return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        extra_save_data = {}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier

        company = Company.objects.get(id=request.user)
        company_name = company.name
        print("\ncompany in QdegreeGraphView : \n", Registry().get(CURRENT_API_COMPANY), "\n")
        from chat.clients.workflows.qdegree import survey_workflow
        print("\nEntered Graph\n")
        respone = survey_workflow.run_workflow(initial_message=text, mobile_number=mobile, session_id=session_id,
                                               client_identifier=client_identifier, company=company)
        print("\nresponse from graph : \n", respone, "\n")

        return JsonResponse({'messages': respone})


class GeetaGraphView(APIView):
    authentication_classes = [ApiKeyAuthentication]

    def post(self, request, format=None):
        company = Company.objects.get(id=request.user)

        langfuse_context.configure(
            secret_key=company.langfuse_secret_key,
            public_key=company.langfuse_public_key
        )

        text = request.data.get('text')
        mobile = request.data.get('mobile')
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')
        if not text:
            return Response({'error': 'No text provided'}, status=400)
        if not mobile:
            return Response({'error': 'Please provide customer mobile number, param mobile missing'}, status=400)
        # if not session_id:
        #     return Response({'error': 'Please provide unique session_id for ongoing conversation'}, status=400)

        extra_save_data = {}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier

        company = Company.objects.get(id=request.user)
        print("\ncompany in GeetaGraphView : \n", Registry().get(CURRENT_API_COMPANY), "\n")
        from chat.clients.workflows.geeta import chat_flow
        print("\nEntered Graph\n")
        api_controller = ApiController.objects.filter(api_route="gvi_chat", company=company).first()
        session_id = SessionManager().generate_session_id(session_type=ApiController.SESSION_TYPE_PER_CALL_ONE_SESSION)
        openmeter_obj = OpenMeter(company=company, api_controller=api_controller, session_id=session_id)
        response = chat_flow.run_workflow(initial_message=text, mobile_number=mobile, session_id=session_id,
                                          client_identifier=client_identifier,
                                          company=company, openmeter_obj=openmeter_obj)
        # openmeter_obj.ingest_api_call(api_method="chat_flow_run_workflow")
        print("\nresponse from graph : \n", response, "\n")
        final_response = ''
        for message in response:
            final_response += message + "\n"
        return JsonResponse({'message': final_response})


class GraphWorkView(TemplateView):
    template_name = 'admin/workflow/graph-workflow.html'

    def get_context_dataq(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        if not self.request.user.has_perm('auth.can_view_graph_workflow'):
            raise PermissionDenied  # Raise 403 error if the user lacks permission
        # Add additional context
        context['name'] = 'Django'
        return context

    def get_context_data(self, **kwargs):
        if not self.request.user.has_perm('auth.can_view_graph_workflow'):
            raise PermissionDenied  # Raise 403 error if the user lacks permission
        return dict(
            site.each_context(self.request),
        )
