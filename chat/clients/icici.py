import re
from .base import BaseOrganization
import chat.utils as utils
import chat.assistants as assistants
import pinecone
import pprint
import json
from rest_framework.response import Response
from rest_framework import status



class Icici(BaseOrganization):
    def process_request(self, request, text, mobile, version='1.0'):
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')

        
        chat_history = utils.fetch_conversation(request.user,mobile,20,True)
        master_response = assistants.get_active_master_prompt(request,chat_history, version)
        role = master_response.get('role', 'assistant')
        function_name = master_response.get('function_name', '')
        extra_save_data = {'function_name': function_name}
        if session_id:
            extra_save_data['session_id'] = session_id
        if client_identifier:
            extra_save_data['client_identifier'] = client_identifier
        utils.save_conversation(request.user,role,mobile,master_response['message'],extra_save_data)

        if 'is_function' in master_response and master_response['is_function'] == True:
            if master_response['function_name'] == "designate_to_policy_expert_assistant":
                chat_history = utils.fetch_conversation(request.user,mobile,10,True)
                expert_response = assistants.get_active_expert_support_prompt(request,chat_history,version)
                if 'is_function' in expert_response and expert_response['is_function'] == True:
                    if expert_response['function_name'] == "search_info":
                        query = expert_response['arguments']['query']
                        extra_save_data = {}
                        extra_save_data = {'function_name':'search_info'}
                        if session_id:
                            extra_save_data['session_id'] = session_id
                        if client_identifier:
                            extra_save_data['client_identifier'] = client_identifier
                        utils.save_conversation(request.user,'function',mobile,expert_response['arguments'],extra_save_data)
                        info = self.search_info(query,5)

                        utils.save_conversation(request.user,'function',mobile,info,extra_save_data)
                        chat_history = utils.fetch_conversation(request.user,mobile,4,True)
                        expert_response = assistants.get_active_expert_support_prompt(request,chat_history,version)
                        print('response recieved from expert second time after policy info', expert_response)
                        extra_save_data = {}
                        if session_id:
                            extra_save_data['session_id'] = session_id
                        if client_identifier:
                            extra_save_data['client_identifier'] = client_identifier
                        print(expert_response)
                        utils.save_conversation(request.user,'assistant',mobile,expert_response,extra_save_data)
                        master_response = {}
                        master_response['message'] = expert_response # type: ignore
                else:
                    extra_save_data = {}
                    if session_id:
                        extra_save_data['session_id'] = session_id
                    if client_identifier:
                        extra_save_data['client_identifier'] = client_identifier
                    utils.save_conversation(request.user,'assistant',mobile,expert_response,extra_save_data)
                    master_response = {}
                    master_response['message'] = expert_response # type: ignore

        return master_response

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
            info += match['metadata']['text']
        return info

    def agent_request(self, request, text,conversation,  mobile):
        session_id = request.data.get('session_id')
        client_identifier = request.data.get('client_identifier')
        chat_history = utils.fetch_conversation(request.user,mobile,8,True)
        if conversation : 
            conversation_as_system_prompt = {
                'role' : 'system',
                'content' : f'Here is the conversation between the insurance agent and the customer for context : {conversation}'
            }
            chat_history.insert(0,conversation_as_system_prompt)

        agent_assistant_response = assistants.get_active_agent_prompt(request,chat_history)
        response = {}
        if 'is_function' in agent_assistant_response and agent_assistant_response['is_function'] == True:
            if agent_assistant_response['function_name'] == "search_info":
                query = agent_assistant_response['arguments']['query']
                if 'plan_name' in agent_assistant_response['arguments']:
                    plan_name = agent_assistant_response['arguments']['plan_name']
                    query = query + " " + plan_name
                extra_save_data = {}
                extra_save_data = {'function_name':'search_info'}
                if session_id:
                    extra_save_data['session_id'] = session_id
                if client_identifier:
                    extra_save_data['client_identifier'] = client_identifier
                utils.save_conversation(request.user,'function',mobile,agent_assistant_response['arguments'],extra_save_data)
                info = self.search_info(query,5)
                utils.save_conversation(request.user,'function',mobile,info,extra_save_data)
                chat_history = utils.fetch_conversation(request.user,mobile,20,True)
                assistant_response = assistants.get_active_agent_prompt(request,chat_history)
                extra_save_data = {}
                if session_id:
                    extra_save_data['session_id'] = session_id
                if client_identifier:
                    extra_save_data['client_identifier'] = client_identifier
                utils.save_conversation(request.user,'assistant',mobile,assistant_response['completion'],extra_save_data)
                response['message'] = assistant_response['completion']
        else:
            extra_save_data = {}
            if session_id:
                extra_save_data['session_id'] = session_id
            if client_identifier:
                extra_save_data['client_identifier'] = client_identifier
            utils.save_conversation(request.user,'assistant',mobile,agent_assistant_response['completion'],extra_save_data)
            response['message'] = agent_assistant_response['completion']

        return response
    
    def summary_request(self, request, conversation , mobile):
        chat_history = []
        conversation_as_system_prompt = {
            'role' : 'system',
            'content' : f'Here is the conversation between the insurance agent and the customer that you need to summarise : {conversation}'
        }
        chat_history.insert(0,conversation_as_system_prompt)
        summary_assistant_response = assistants.get_summary_prompt(request,chat_history)
        session_id = request.data.get('session_id')
        utils.save_summary(summary_assistant_response['completion'], mobile, session_id)
        response = {}
        response['message'] = summary_assistant_response['completion']

        return response
 
    def actionables_request(self, request, conversation , mobile):
        session_id = request.data.get('session_id')
        chat_history = []
        conversation_as_system_prompt = {
            'role' : 'system',
            'content' : f'Here is the conversation between the insurance agent and the customer to create action points : {conversation}'
        }
        chat_history.insert(0,conversation_as_system_prompt)
        actionables_assistant_response = assistants.get_further_actions_prompt(request,chat_history)
        cleaned_data = {}
        try:
            actionables_string = re.sub(r'```json\n|\n```', '', actionables_assistant_response['completion'])
            actionables_object = json.loads(actionables_string)
            schema_actions = utils.get_post_call_actionables_schema().value['actions']
            ai_actions = actionables_object['actions']
            updated_actions = []

            for schema_action, ai_action in zip(schema_actions, ai_actions):
                if schema_action['type'] == ai_action['type']:
                    merged_action = schema_action.copy()
                    merged_action['description'].update(ai_action.get('description', {}))
                    updated_actions.append(merged_action)
                else:
                    updated_actions.append(schema_action)


            def clean_json(data):
                if isinstance(data, dict):
                    return {
                        key: clean_json(value)
                        for key, value in data.items()
                        if value is not None and clean_json(value) != {}
                    }
                elif isinstance(data, list):
                    return [clean_json(item) for item in data if clean_json(item) != {}]
                else:
                    return data
               
            cleaned_data = clean_json(updated_actions)

            def remove_type_only_objects(data):
                return [item for item in data if len(item) > 1]
            
            cleaned_data = remove_type_only_objects(cleaned_data)
            utils.save_actionables(updated_actions, mobile, session_id)
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error processing actionables data: {e}")
            cleaned_data = {}

        return cleaned_data
    
    def sen_analysis_request(self, request, conversation , mobile):
        chat_history = []
        conversation_as_system_prompt = {
            'role' : 'system',
            'content' : f'Here is the conversation between the insurance agent and the customer to do Sentiment analysis : {conversation}'
        }
        chat_history.insert(0,conversation_as_system_prompt)
        summary_assistant_response = assistants.get_sentimental_analysis_prompt(request,chat_history)
        response = {}
        try:
            sentimental_analysis = json.loads(summary_assistant_response['completion'])
            score = sentimental_analysis[0].get("score")
            emotion = sentimental_analysis[1].get("emotion")
            
            analysis_result = {
                'score' : score,
                'emotion' : emotion
            }
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            analysis_result = {
                'score' : 8,
                'emotion' : 'neutral'
            }

        response['message'] = analysis_result

        return response
    
    def profile_update_request(self, request, conversation, mobile):
        chat_history = []
        conversation_as_system_prompt = {
            'role' : 'system',
            'content' : f'Here is the conversation between the insurance agent and the customer to fetch user data from : {conversation}'
        }
        chat_history.insert(0,conversation_as_system_prompt)
        assistant_response = assistants.get_profile_data_prompt(request,chat_history)
        profile_data_string = re.sub(r'```json\n|\n```', '', assistant_response['completion'])
        profile_schema = utils.get_customer_profile_schema().value

        def generate_delta(original_profile, new_profile):
            delta = {}
            def _generate_delta(original, new, path=""):
                for key, value in new.items():
                    if key not in original or original[key] != value:
                        if path:  # Handle nested paths
                            current_path = path + "." + key 
                        else:
                            current_path = key 

                        if isinstance(value, dict):
                            _generate_delta(original.get(key, {}), value, current_path)
                        else:
                            *parent_path, last_key = current_path.split(".")
                            parent_dict = delta
                            
                            for part in parent_path:
                                parent_dict.setdefault(part, {})
                                parent_dict = parent_dict[part]
                            
                            parent_dict[last_key] = value

            _generate_delta(original_profile, new_profile)
            return {"customer_profile_attributes": delta}
        
        def update_profile(schema, data, path=""):
            for schema_key, schema_value in schema.items():
                current_path = f"{path}.{schema_key}" if path else schema_key
                data_key = next((k for k in data.keys() if k.lower() == schema_key.lower()), None)
                
                if data_key is None:
                    print(f"No matching key found for {current_path}")
                    continue
                
                if isinstance(schema_value, dict):
                    if isinstance(data[data_key], dict):
                        update_profile(schema_value, data[data_key], current_path)
                    else:
                        print(f"Mismatch at {current_path}: schema expects dict, got {type(data[data_key])}")
                elif data[data_key] is not None:
                    print(f"Updating {current_path}: {schema[schema_key]} -> {data[data_key]}")
                    schema[schema_key] = data[data_key]
                else:
                    print(f"Skipping {current_path}: value is None")
        try:
            profile_data = json.loads(profile_data_string)
            existing_profile_data = utils.get_customer_profile_temp(mobile)
            if existing_profile_data:
                delta = generate_delta(
                    existing_profile_data['customer_profile_attributes'],  # type: ignore
                    profile_data['customer_profile_attributes']
                )
            update_profile(profile_schema['customer_profile_attributes'], profile_data['customer_profile_attributes'])
            if not existing_profile_data:
                delta = profile_schema
            utils.save_customer_profile_temp(profile_schema, mobile)
            response_data = {
                "profile_data": profile_schema,
                "delta": delta
            }
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error processing profile data: {e}")
            response_data = {
                "profile_data": {},
                "delta": {}
            }

        return response_data
    
    def profile_update_request_manual(self, profile_data, mobile):
        try:
            profile_data = json.loads(profile_data)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
             return {f"JSON error : {e}"}
        profile_schema = utils.get_customer_profile_schema().value
        def update_profile(schema, data, path=""):
            for schema_key, schema_value in schema.items():
                current_path = f"{path}.{schema_key}" if path else schema_key
                data_key = next((k for k in data.keys() if k.lower() == schema_key.lower()), None)
                
                if data_key is None:
                    print(f"No matching key found for {current_path}")
                    continue
                
                if isinstance(schema_value, dict):
                    if isinstance(data[data_key], dict):
                        update_profile(schema_value, data[data_key], current_path)
                    else:
                        print(f"Mismatch at {current_path}: schema expects dict, got {type(data[data_key])}")
                elif data[data_key] is not None:
                    print(f"Updating {current_path}: {schema[schema_key]} -> {data[data_key]}")
                    schema[schema_key] = data[data_key]
                else:
                    print(f"Skipping {current_path}: value is None")
        try: 
            update_profile(profile_schema['customer_profile_attributes'], profile_data['customer_profile_attributes'])
            # utils.save_customer_profile(profile_schema, mobile)
            utils.save_customer_profile_temp(profile_schema, mobile)
            return {"modified"}
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            return {"failed"}
            
    def evaluate_agent_request(self, request, agent_reference_id, duration=1):
        chat_history = []
        previous_summaries = utils.get_previous_agent_summaries(agent_reference_id,duration)
        summaries_as_system_prompt = {
            'role' : 'system',
            'content' : f'Here are the summaries of the insurance agent and the customer that you need to evaluate : {previous_summaries}'
        }
        chat_history.insert(0,summaries_as_system_prompt)
        evaluation = assistants.get_agent_evaluation_prompt(request,chat_history)
        try:
            evaluation_string = re.sub(r'```json\r?\n|```\r?\n?', '', evaluation['completion'], flags=re.MULTILINE)
            evaluation_schema = utils.get_agent_performance_schema().value['evaluation']
            evaluation_object = json.loads(evaluation_string)
            ai_evaluation = evaluation_object['evaluation']

            def update_schema(schema, data):
                for key, value in schema.items():
                    if isinstance(value, dict):
                        if key in data:
                            update_schema(value, data[key])
                    else:
                        if key in data:
                            schema[key] = data[key]

            update_schema(evaluation_schema, ai_evaluation)
            utils.save_agent_evaluation(agent_reference_id,evaluation_schema)
            return evaluation_schema
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f'error evaluating agent {e}')
            return {}