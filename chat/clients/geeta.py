import re
from .base import BaseOrganization
import chat.utils as utils
import chat.assistants as assistants
import pinecone
from rest_framework.response import Response
from rest_framework import status


class Geeta(BaseOrganization):
    def process_request(self, request, text, mobile, version='1.0'):
        chat_history = utils.fetch_conversation(request.user,mobile,14,True)
        expert_response = assistants.get_active_expert_support_prompt(request,chat_history,version)
        final_response = {}
        if 'is_function' in expert_response and expert_response['is_function'] == True:
            if expert_response['function_name'] == "search_info":
                query = expert_response['arguments']['query']
                extra_save_data = {}
                extra_save_data = {'function_name':'search_info'}
                utils.save_conversation(request.user,'function',mobile,expert_response['arguments'],extra_save_data)
                info = self.search_info(query,2)
                utils.save_conversation(request.user,'function',mobile,info,extra_save_data)
                chat_history = utils.fetch_conversation(request.user,mobile,14,True)
                second_response = assistants.get_active_expert_support_prompt(request,chat_history,version)
                extra_save_data = {}
                utils.save_conversation(request.user,'assistant',mobile,second_response['completion'],extra_save_data)
                final_response['message'] = second_response['completion']
        else:
            extra_save_data = {}
            utils.save_conversation(request.user,'assistant',mobile,expert_response['completion'],extra_save_data)
            final_response['message'] = expert_response['completion']

        return final_response

    def search_info(self, query, topk):
        query_embedding = utils.create_embedding(query)
        vectordb_host = utils.get_vectordb_host()
        vector_db_init = utils.init_vectordb_host(vectordb_host)
        if not (vector_db_init):
            #raise exception
            pass
        
        index = pinecone.Index(vector_db_init) #type:ignore
        response = index.query(vector=query_embedding,top_k=topk, include_metadata=True)
        matches = response['matches']
        info = ''
        for match in matches:
            data = match['metadata']
            for key, value in data.items():
                info += key + ' : '
                info += value + ' '
        return info