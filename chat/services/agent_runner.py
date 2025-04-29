import requests
from chat.models import Conversations, Prompt
from chat.serializers import ConversationSerializer
from chat.factory import get_llm_class
from django.core.exceptions import ObjectDoesNotExist
from services.services.rest_api_agent import RestAPIAgent
from services.models import APIEndpoint
from services.response_processor import BaseResponseProcessor


class BaseAgentRunner:

    def fetch_conversation(self, company, mobile, limit=14, start_from_hello=False):
        if company:
            chat_history = Conversations.without_company_objects.filter(mobile=mobile).order_by('-created_at')[:limit]
        else:
            chat_history = Conversations.objects.filter(mobile=mobile).order_by('-created_at')[:limit]


        if start_from_hello:
            latest_hello_index = None
            for index, conversation in enumerate(chat_history):
                if conversation.role == 'user' and conversation.message.lower() in ['hi', 'hello', 'hello\n']:
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
        function_message_index = [0, 1]
        for index, conversation in enumerate(filtered_conversations):  # type: ignore
            if conversation.role != 'function' or index in function_message_index:
                final_conversation.append(conversation)
                # break

        serializer = ConversationSerializer(final_conversation, many=True)
        req_chat_history = serializer.data

        custom_data = []
        for item in req_chat_history:
            entry = {'role': item['role'], 'content': item['message']}
            if 'function_name' in item and item['function_name']:
                entry['name'] = item['function_name']
            custom_data.append(entry)

        return custom_data

    """Here Version is Hard Coded Because we are selecting Master Prompt"""

    def get_active_master_prompt(self, client, chat_history, version='1.0'):
        return self.get_active_prompt(Prompt.PROMPT_TYPE_MASTER_ASSISTANT, client, chat_history,
                                      'process_master_response',
                                      version=version)

    def get_active_prompt(self, prompt_type, client, chat_history, process_response_method='process_response',
                          version='1.0'):
        try:
            prompt = Prompt.objects.get(prompt_type=prompt_type, active=True, version=version)
            print("prompt", prompt.id, prompt.llm)
            llm_class = get_llm_class(prompt.llm)
            # breakpoint()
            llm_class_response = llm_class.process_request(client, prompt.content, prompt.functions, prompt.model,
                                                           chat_history)
            llm_class_completion = getattr(llm_class, process_response_method)(llm_class_response)

            return llm_class_completion
        except Prompt.DoesNotExist:
            raise ObjectDoesNotExist(f"{prompt_type.replace('_', ' ').title()} not found")

    def save_conversation(self, client, role, mobile, text, extra={}):
        if not text:
            return "Something Went Wrong, Try again!, Empty message from AI"
        if 'function_return' in extra:
            text += f"\nFunction Return: {extra['function_return']}"
            extra.pop('function_return')

        new_conversation = Conversations(
            role=role,
            mobile=mobile,
            message=text,
            **extra,
        )
        new_conversation.save()

    # create seperate class for this, in Services App


class AgentRunner(BaseAgentRunner, RestAPIAgent):

    def initiate_request(self, user, message, extra_save_data):
        """Saving current message in conversation"""
        self.save_conversation(user, 'user', user.mobile_number, message, extra_save_data)
        chat_history = self.fetch_conversation(user, user.mobile_number, start_from_hello=True)
        """Every Company must have its Master Assistant"""
        master_assistant = self.get_active_master_prompt(user, chat_history)
        # breakpoint()
        role = master_assistant.get('role', 'assistant')
        function_name = master_assistant.get('function_name', '')
        self.save_conversation(user, role, user.mobile_number, master_assistant['message'],
                               {'function_name': function_name})
        print("master_assistant", master_assistant)
        """Master Prompt Post Processing"""
        if 'is_function' in master_assistant and master_assistant['is_function'] == True:
            _master_assistant_func_name = master_assistant.get("function_name").replace("designate_to_", "")
            print("- In Master Prompt ", _master_assistant_func_name)
            """
                Json changes
                designate_to_order_assistant >> order_query_assistant
                
                - In below function calling prompt suggested by master prompt
            """
            order_response = self.get_active_prompt(_master_assistant_func_name, user, chat_history)
            _child_prompt_action = order_response.get('function_name', None)
            print("-- child Prompt  actions ", _child_prompt_action, order_response)
            api_response = self.invoke_agent(_child_prompt_action, {'user_id': 629},
                                                    ai_args=order_response.get("arguments", {}))
            if api_response:
                self.save_conversation(user, 'function', user.mobile_number, master_assistant['message'],
                                       {'function_name': _child_prompt_action,
                                        'function_return': api_response})
                chat_history = self.fetch_conversation(user, user.mobile_number)
                order_response = self.get_active_prompt(_master_assistant_func_name, user, chat_history)

            self.save_conversation(user, 'assistant', user.mobile_number, order_response['completion'])
            if order_response['completion']:
                master_assistant['message'] = str(order_response['completion'])
            else:
                master_assistant['message'] = "Can't able to process it for now, Try Again"
            # below line must be removed it for testing only
            if str(api_response):
                master_assistant['message'] + "\n" + str(api_response)

            """
                ## recent_order_data = self.recent_orders(request)
                ## utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                ##                         {'function_name': 'get_recent_orders',
                ##                          'function_return': recent_order_data})
                ## chat_history = utils.fetch_conversation(request.user, mobile)
                
                # order_response = assistants.get_active_order_prompt(request, chat_history)
                # utils.save_conversation(request.user, 'assistant', mobile, order_response['completion'])
                # master_response['message'] = order_response['completion']
            """

        return master_assistant.get("message")
