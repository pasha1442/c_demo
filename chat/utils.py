import json
import os
from basics.services.gcp_bucket_services import GCPBucketService
from chat import factory
from chat.clients.workflows.workflow_runner import WorkflowRunner
from chat.constants import USE_IMAGE_URL_FOR_ANALYSIS
from chat.serializers import * 
from openai import OpenAI
import pinecone
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from company.models import Company, CompanyCustomer, CompanyEntity, CompanyPostProcessing, CompanySetting
from django.db.models import Max, F
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from django.db.models import JSONField, F
from django.db.models.functions import Cast
from django.utils.timezone import now
from langchain_core.messages import AIMessage, HumanMessage, FunctionMessage, SystemMessage
from langfuse.decorators import observe, langfuse_context
from decouple import config
import base64
from urllib.parse import urlparse
from company.utils import CompanyUtils

@observe
def encode_image(image_path):
    ''' Getting the base64 string '''
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

@observe()
def save_conversation(company, role, mobile, text, message_metadata={}, extra={}, return_instance=False):
    if 'function_return' in extra:
        text += f"\nFunction Return: {extra['function_return']}"
        extra.pop('function_return')
    if "message_metadata" in extra.keys():
        new_conversation = Conversations(
            company=company,
            role=role,
            mobile=mobile,
            message=text,
            **extra,
        )
    else:
        new_conversation = Conversations(
            company=company,
            role=role,
            mobile=mobile,
            message=text,
            message_metadata=message_metadata,
            **extra,
        )

    new_conversation.save()
    if return_instance:
        return new_conversation.id

@observe()
def fetch_conversation(company, mobile, limit=14, start_from_hello=False):
    if company:
        chat_history = Conversations.without_company_objects.filter(mobile=mobile).order_by('-created_at')[:limit]
    else:
        chat_history = Conversations.objects.filter(mobile=mobile).order_by('-created_at')[:limit]
    if start_from_hello:
        latest_hello_index = None
        for index, conversation in enumerate(chat_history):
            if conversation.role == 'user' and any(greeting in conversation.message.lower() for greeting in ['hello']):
                latest_hello_index = index
                break

        if latest_hello_index is not None and latest_hello_index < limit:
            filtered_conversations = chat_history[:latest_hello_index + 1]
        else:
            filtered_conversations = chat_history
    else:
        filtered_conversations = chat_history
    
    final_conversation = []

    # add only the first function to chat history, rest can be ignored
    # function_message_index = [0,1]
    # for index, conversation in enumerate(filtered_conversations): # type: ignore
    #     if conversation.role != 'function' or index in function_message_index:
    #         final_conversation.append(conversation)
    #         # break
    for conversation in filtered_conversations:
        final_conversation.append(conversation)

    serializer = ConversationSerializer(final_conversation, many=True)
    req_chat_history = serializer.data

    custom_data = []
    for item in req_chat_history:
        entry = {'role': item['role'], 'content': item['message']}
        if 'function_name' in item and item['function_name']:
            entry['name'] = item['function_name']
        custom_data.append(entry)

    return custom_data

def fetch_conversation_by_session_id(session_id, company=None):
    if company:
        CompanyUtils.set_company_registry(company=company)
        
    conversation = Conversations.objects.filter(session_id=session_id).order_by('-created_at')
    serializer = ConversationSerializer(conversation, many=True)
    cleaned_chat_history = serializer.data

    return cleaned_chat_history


@observe()
def strucutre_conversation_langchain(chat_history: list, send_tool_args = True, reverse=True, openmeter_obj = None) -> list:
    enabled_media_in_chat_history = False
    if openmeter_obj:
        enabled_media_in_chat_history = openmeter_obj.api_controller.enabled_media_in_chat_history
    
    messages = []
    history = reversed(chat_history) if reverse else chat_history
    gcp_bucket_service = GCPBucketService()
    for message in history:
        if message['role'] == 'function' and send_tool_args:
            messages.append((FunctionMessage(name = message['name'], content=message['content'])))
        elif message['role'] == 'user' :
            if (enabled_media_in_chat_history and 'message_metadata' in message and message['message_metadata'] and 'media_url' in message['message_metadata'] and message['message_metadata']['media_url']):
                media_urls = message['message_metadata']['media_url']
                if isinstance(media_urls, str):
                    media_urls = media_urls.split(",")
                for url in media_urls:
                    if USE_IMAGE_URL_FOR_ANALYSIS:
                        parsed_url = urlparse(url)
                        url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                        messages.append(HumanMessage(content=[
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": url
                                    },
                                },
                            ]))
                    else:
                        base64_image = base64.b64encode(gcp_bucket_service.download_from_url_in_bytes(url)).decode("utf-8")
                        messages.append(HumanMessage(content=[
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    },
                                },
                            ]))
            
            messages.append(HumanMessage(content=message['content']))
        elif message['role'] == 'assistant':
            messages.append(AIMessage(content=message['content']))
        elif message['role'] == 'system':
            messages.append(SystemMessage(content=message['content']))

    return messages

def has_service(user, service_id):
    return user.services.filter(id=service_id).exists()

@observe()
def create_embedding(text):
    api_key = os.getenv('OPEN_AI_KEY')
    if not api_key:
        raise ValueError("OPEN_AI_KEY environment variable not set")
    
    os.environ['OPENAI_API_KEY'] = f"{api_key}"
    client = OpenAI()
    # client.api_key = OPENAI_API_KEY # type: ignore
    response = client.embeddings.create(
        input = text,
        model = "text-embedding-ada-002"
    )
    embeddings = response.data[0].embedding #type:ignore
    return embeddings

@observe()
def get_vectordb_host():
    vectordb_host = CompanySetting.objects.get(key="vectordb")
    return vectordb_host.value['host']

@observe()
def get_customer_profile_schema():
    customer_profile_schema = CompanySetting.objects.get(key="customer_profile_schema")
    return customer_profile_schema

@observe()
def get_post_call_actionables_schema():
    actionables_schema = CompanySetting.objects.get(key="post_processing_schema")
    return actionables_schema

@observe()
def get_customer_profile(mobile):
    customer_profile_data = CompanyCustomer.objects.get(mobile=mobile)
    return customer_profile_data.profile_data

@observe()
def get_customer_profile_temp(mobile):
    try:
        customer_profile_data = CompanyEntity.objects.get(reference_id=mobile, type="customer")
        return customer_profile_data.data
    except CompanyEntity.DoesNotExist:
        return get_customer_profile_schema().value

@observe()
def init_vectordb_host(vectordb_host):
    if(vectordb_host == 'pinecone'):
        credentials = CompanySetting.objects.get(key="pinecone")
        credentials_dict = {k: v for d in credentials.value for k, v in d.items()}
        pinecone.init(
            api_key = credentials_dict.get('api_key'), # type: ignore
            environment = credentials_dict.get('environment') # type: ignore
        )
        index_name = credentials_dict.get('index')
        namespace = credentials_dict.get('namespace')
        if namespace:
            return {'index_name':index_name, 'namespace':namespace}
        return index_name
    elif(vectordb_host == 'chroma'):
        pass
    else:
        pass
    
    return False

@observe()
def save_customer_profile(profile, mobile):
    try:
        customer, created = CompanyCustomer.objects.get_or_create(mobile=mobile)

        if customer.profile_data is None:
            customer.profile_data = profile
        else:
            customer.profile_data.update(profile)

        customer.save()
        print("Customer profile saved/updated successfully.")
    except Exception as e:
        print(f"Error saving customer profile: {e}")

@observe()
def save_customer_profile_temp(profile, mobile, company=None):
    try:
        customer, created = CompanyEntity.objects.get_or_create(reference_id=mobile,type="customer",defaults={'desc': "Default description"})

        if customer.data is None:
            customer.data = profile
        else:
            customer.data.update(profile)
        print("\nInside save feedback util\nprofile= ", profile,"\n\nmobile= ",mobile,"\n\ncompany= ", company,"\n")
        customer.save(company=company)
        print("**NEW**Customer profile saved/updated successfully.")
    except Exception as e:
        print(f"Error saving customer profile: {e}")

@observe()
def save_summary(summary, mobile, session_id):
    try:
        customer, created = CompanyPostProcessing.objects.get_or_create(session_id=session_id)
        print('created summary',created)
        if created:
            customer.session_nature = "call"
            customer.action = CompanyPostProcessing.ActionChoices.NO_ACTION
            customer.client_session_ref_id = session_id
            customer.data = { # type: ignore
                "actions": [
                ],
                "summary": {},
                "agent_reference_id": "",
            }

        if customer.data:
            customer.data['summary'] = summary 
        else:
            customer.data = {"summary": summary}  # type: ignore

        customer.save()
        print("post  processing summary saved/updated successfully.")
    except Exception as e:
        print(f"Error saving customer profile: {e}")

@observe()
def save_actionables(actions, mobile, session_id):
    try:
        customer, created = CompanyPostProcessing.objects.get_or_create(session_id=session_id)

        if created:
            customer.session_nature = "call"
            customer.action = CompanyPostProcessing.ActionChoices.NO_ACTION
            customer.client_session_ref_id = session_id
            customer.data = { # type: ignore
                "actions": [
                ],
                "summary": {},
                "agent_reference_id": "",
            }

        if customer.data:
            customer.data['actions'] = actions 
        else:
            customer.data = {"actions": actions}  # type: ignore

        customer.save()
        print("post  processing actions saved/updated successfully.")
    except Exception as e:
        print(f"Error saving customer profile: {e}")


# @observe()
def get_user_sessions_orm(mobile):
    session_ids = (
        Conversations.objects.filter(mobile=mobile)
        .values('session_id')
        .annotate(latest_created=Max('created_at'))
        .order_by('-latest_created')
        .values_list('session_id', flat=True)
        [:10]
    )
    if not session_ids:
        return {}
    
    session_data = CompanyPostProcessing.objects.filter(session_id__in=session_ids).order_by('-created_at').values('session_id','created_at','data','action','session_nature')[:10]
    return session_data


def fetch_session_history(mobile):
    session_data = get_user_sessions_orm(mobile)
    if not session_data:
        return {}

    now = datetime.now(timezone.utc)

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7_days = today - timedelta(days=7)
    start_of_month = today.replace(day=1)
    
    organized_conversations = defaultdict(lambda: {'total_conversations': 0, 'conversations': []})

    def start_of_previous_months(n, start_month):
        months = []
        for i in range(n):
            month = (start_month - timedelta(days=1)).replace(day=1)
            months.append(month)
            start_month = month
        return months

    previous_months = start_of_previous_months(6, start_of_month)

    def get_day_with_suffix(day):
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        return str(day) + suffix
    
    sorted_session_data = sorted(session_data, key=lambda x: x['created_at'], reverse=True)
    
    for conversation in sorted_session_data:
        created_at = conversation['created_at']
        summary = conversation['data']['summary']
        actions = conversation['data']['actions']
        session_id = conversation['session_id']
        day_with_suffix = get_day_with_suffix(created_at.day)
        date = f"{day_with_suffix} {created_at.strftime('%B')}"
        time = created_at.strftime('%H:%M')

        if created_at >= today:
            key = 'today'
        elif created_at >= last_7_days:
            key = 'last_7_days'
        elif created_at >= start_of_month:
            key = 'this_month'
        else:
            for month in previous_months:
                if created_at >= month:
                    key = month.strftime('%B %Y')
                    break

        organized_conversations[key]['total_conversations'] += 1 # type: ignore
        organized_conversations[key]['conversations'].append({ # type: ignore
            'session_id': session_id,
            'summary': summary,
            'actions': actions,
            'date': date,
            'time': time
        })

    organized_conversations = dict(organized_conversations)
    return organized_conversations

@observe()
def extract_json_from_string(text):
    """Extracts the first valid JSON object found in the given string."""
    try:
        start_index = text.index("{")
        bracket_count = 1
        for i in range(start_index + 1, len(text)):
            if text[i] == "{":
                bracket_count += 1
            elif text[i] == "}":
                bracket_count -= 1
                if bracket_count == 0:
                    end_index = i + 1
                    break
        # Extract and parse the JSON substring
        json_substring = text[start_index:end_index]
        return json.loads(json_substring)
    except (json.JSONDecodeError, ValueError):
        return None
    
@observe()
def get_previous_agent_summaries(reference_id, months = 1):

    if months is None or not isinstance(months, int):
        months = 1

    cutoff_date = now() - timedelta(days=30 * months)

    results = CompanyPostProcessing.objects.annotate(
        data_json=Cast('data', JSONField())
    ).filter(
        data_json__agent_reference_id=reference_id,
        created_at__gte=cutoff_date
    ).values(
        summary=F('data_json__summary')
    )
    return list(results)

@observe()
def get_agent_performance_schema():
    agent_performance_schema = CompanySetting.objects.get(key="agent_performance_schema")
    return agent_performance_schema

@observe()
def get_agent_data(reference_id):
    try:
        agent_data = CompanyEntity.objects.get(reference_id=reference_id, type="agent")
        return agent_data.data
    except CompanyEntity.DoesNotExist as e:
        print(f'error fetching agent with reference id {reference_id} {e}')
        return get_agent_performance_schema().value
    
@observe()
def save_agent_evaluation(agent_reference_id, data):
    try:
        customer, created = CompanyEntity.objects.get_or_create(reference_id=agent_reference_id,type="agent")

        if created:
            customer.data = { # type: ignore
                "profile": {},
                "evaluation": {},
            }

        if customer.data:
            customer.data['evaluation'] = data 
        else:
            customer.data = {"evaluation": data}  # type: ignore

        customer.save()
        print("**NEW** Agent profile saved/updated successfully.")
    except Exception as e:
        print(f"Error saving customer profile: {e}")

@observe()
def fetch_shloka_from_geeta(shloka_no):
    vectordb_host = get_vectordb_host()
    vector_db_init = init_vectordb_host(vectordb_host)
    if not (vector_db_init):
        #raise exception
        pass
    index = pinecone.Index(vector_db_init) # type: ignore
    response = index.query(id=shloka_no,top_k=1, include_metadata=True)
    matches = response['matches']
    return matches[0]['metadata']

def get_company_whatsapp_provider(company=None):
    if company:
        wa_provider = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_WHATSAPP_PROVIDER,
                                                                 company=company)
    else:
        wa_provider = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_WHATSAPP_PROVIDER)
    return wa_provider.value['provider']

def get_company_whatsapp_creds(company=None):
    if company:
        provider_creds = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_WHATSAPP_PROVIDER,
                                                                    company=company)
    else:
        provider_creds = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_WHATSAPP_PROVIDER)
    return provider_creds.value

# @observe()
def handle_webhook_message(company: Company, request, data, openmeter_obj, workflow_name):

    # allowed asynchronous?
    # if not sending message in realtime
    if not data['text'] or not data['customer_mobile']:
        return
    
    message_data = {
        'text' : data['text'],
        'mobile_number': data['customer_mobile'],
        'message_type' : data['message_type'],
        'message_id' : data['message_id'],
        'message_metadata' : {'media_url' : data.get('media_url')} 
    }
    session_id = openmeter_obj.billing_session_id
    company_workflow = factory.get_specific_workflow(company.name, workflow_name)
    company_workflow_response = company_workflow.run_workflow(initial_message=data['text'],mobile_number=data['customer_mobile'],session_id=session_id,client_identifier=data['client_identifier'],company=company, openmeter_obj = openmeter_obj, message_data=message_data, whatsapp_provider=data['provider_class'])
 
    return company_workflow_response

@observe()
async def handle_dynamic_webhook_message(company: Company, api_controller, data, openmeter_obj, workflow_name):
    # allowed asynchronous?
    # if not sending message in realtime
    if not data['customer_mobile']:
        return
    
    message_data = {
        'text': data['text'],
        'mobile_number': data['customer_mobile'],
        'message_type': data['message_type'],
        'message_id': data['message_id'],
        'message_metadata': {'media_url' : data.get('media_url')},
        'company_phone_number': data.get('company_phone_number', None)
    }

    chat_history_service = InMemoryChatHistoryService(company=company, api_controller=api_controller, start_message=data['text'], media_url=data.get('media_url', ""))
    session_data = chat_history_service.validate_conversation_session(company=company, client_identifier=data['client_identifier'])
    session_id = session_data['session_id']
    print("session id inside utils:", session_id)
    tag = config("CURRENT_ENVIRONMENT")
    # session_id = openmeter_obj.billing_session_id
    workflow_name = company.name.lower().replace(" ", "_") + "_" + api_controller.api_route
    langfuse_context.update_current_trace(user_id=data['customer_mobile'], session_id=session_id, name=workflow_name, tags=[tag])
    workflow_json = api_controller.graph_json
    workflow_type = api_controller.workflow_type
    workflow_stream = api_controller.workflow_stream
    workflow_obj = WorkflowRunner()
    response = ''
    
    client_session_id = ''
    message_provider = {'source': data['source']}
    if message_provider.get('source') == 'waha':
        client_session_id = data.get('waha_session')
        message_provider['company_phone_number'] = data.get('company_phone_number', None)
        message_provider['waha_session'] = data.get('waha_session')
        
        message_data['waha_session'] = data.get('waha_session')
    else:
        message_provider['service_provider_company'] = data.get('service_provider_company', None)
        message_provider['company_phone_number'] = data.get('company_phone_number', None)
        client_session_id = data['customer_mobile']

    async for res in workflow_obj.run_workflow(workflow_name, workflow_json, workflow_type, workflow_stream, initial_message=data['text'],
                                               mobile_number=data['customer_mobile'],
                                               session_id=session_id,
                                               client_session_id=client_session_id,
                                               client_identifier=data['client_identifier'], company=company,
                                               openmeter_obj=openmeter_obj,  message_data=message_data,
                                               message_payload={"session_validated":True},
                                               message_provider = message_provider
                                                ):
        response = res
    return response

def get_content_type_from_url(media_url : str) -> str:
    _, file_extension = os.path.splitext(media_url.lower())
    if file_extension == '.png':
        content_type = 'image/png'
    else:
        content_type = 'image/jpeg'

    return content_type


def update_conversation_message_metadata(session_id, ticket_id):
    conversations = Conversations.objects.filter(session_id=session_id).exclude(message_type='text')
    
    for conversation in conversations:
        if 'ticket_id' not in conversation.message_metadata:
            conversation.message_metadata['ticket_id'] = ticket_id
        
    Conversations.objects.bulk_update(conversations, fields=['message_metadata'])
    
    


# def profanity_free(message):
#     try :
#         guard = Guard().use(
#             ProfanityFree, on_fail="noop"
#         )
#         result = guard.validate(message)
#         return result.validation_passed
#     except Exception as e:
#         print(f"Profanity Free Guardral Error: {e}")

# def check_competitor(message):
#     try:
#         guard = Guard().use(
#             CompetitorCheck(competitors=["apple", "microsoft"], on_fail="fix")
#         )
#         # message = "apple microsoft good enough"
#         result = guard.validate(message).validated_output
#
#         return result if len(result) > 0 else message
#     except Exception as e:
#             print(f"Competitor Check Guardral Error: {e}")
#
# def input_safety_check(message):
#     #Add more guardrails checking here
#     return profanity_free(message)
#
# def get_safe_response(result):
#     if profanity_free(result.content):
#         result.content = "Inappropriate content found in llm response!"
#
#     return result


# class SafeResponseCallback(BaseCallbackHandler):
#     def on_llm_end(self, response, **kwargs):
#         if response.generations[0][0].text:
#             if profanity_free(response.generations[0][0].message.content) == False:
#                 response.generations[0][0].message.content = "Inappropriate content found in llm response! FINAL ANSWER"
#
#             response.generations[0][0].message.content = check_competitor(response.generations[0][0].message.content)
#
#     def raise_error(self, error):
#         print(f"Error occurred: {error}")


# #This is not working yet
# class SafeInputCallback(BaseCallbackHandler):
#
#     def on_chat_model_start(
#         self, serialized: Dict[str, Any], messages: List[List[BaseMessage]], **kwargs: Any
#     ):
#
#         message = messages[-1][-1].content
#         if profanity_free(message) == True:
#             print("Input contains prohibited content. Aborting LLM call.")
#             return False
#         print("Condition met. Proceeding with LLM call.")
#         return True
#
#
#     def raise_error(self, error):
#         print(f"Error occurred: {error}")
