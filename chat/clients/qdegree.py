
import re
import chat.assistants as assistants
import chat.utils as utils
from chat.clients.base import BaseOrganization
from django.core.exceptions import ObjectDoesNotExist 

class Qdegree(BaseOrganization):
    def process_request(self, request, text, mobile, version='1.0'):
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')

        extra_save_data = {}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier

        if text and mobile:
            utils.save_conversation(request.user,'user', mobile, text, extra_save_data)

        chat_history = utils.fetch_conversation(request.user,mobile,25,True)

        latest_survey_id = self.extract_latest_survey_id(chat_history)

        survey_bot_response = assistants.get_active_prompt_by_id(id=latest_survey_id, client=request,chat_history=chat_history, version=version)
        if 'is_function' in survey_bot_response and survey_bot_response['function_name'] == "save_feedback":

            qna = survey_bot_response['arguments']
            extra_save_data = {}
            extra_save_data = {'function_name':'save_feedback'}
            utils.save_conversation(request.user,'assistant',mobile,survey_bot_response['arguments'],extra_save_data)

            saved_feedback = self.save_feedback(qna,mobile)

            utils.save_conversation(request.user,'function',mobile,"Survey data saved for user",extra_save_data)
            second_response = {}
            if('completion' in survey_bot_response and survey_bot_response['completion']):
                second_response['completion'] = survey_bot_response['completion'] # type: ignore
            else:
                chat_history = utils.fetch_conversation(request.user,mobile,25,True)
                second_response = assistants.get_active_prompt_by_id(id=latest_survey_id, client=request,chat_history=chat_history, version=version)
            extra_save_data = {}
            utils.save_conversation(request.user,'assistant',mobile,second_response['completion'],extra_save_data) # type: ignore
            survey_bot_response['message'] = second_response['completion'] # type: ignore
        else:
            extra_save_data = {}
            utils.save_conversation(request.user,'assistant',mobile,survey_bot_response['completion'],extra_save_data)
            survey_bot_response['message'] = survey_bot_response['completion']
             

        return survey_bot_response
    
    def save_feedback(self,qna,mobile):
        feedback = qna
        utils.save_customer_profile_temp(feedback, mobile)
        return feedback
    
    def extract_latest_survey_id(self,chat_history):
        pattern = r'survey_id:(\d+)'
        
        for message in reversed(chat_history):
            if message['role'] == 'user':
                matches = re.findall(pattern, message['content'])
                if matches:
                    return int(matches[0])
        
        raise ValueError("No survey_id found in the chat history.")