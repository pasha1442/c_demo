from datetime import datetime
from typing import Annotated, Dict, List
from langchain_core.tools import tool
from chat import utils
from chat.clients.workflows.agent_state import PipelineState
from company.utils import CompanyUtils
from services.services.base_agent import BaseAgent
from basics.services.gcp_bucket_services import GCPBucketService
from langgraph.prebuilt import InjectedState
import pytz

import json
import traceback
from basics.custom_exception import APIConnectionError

from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)


@tool()
def prepare_movie_recommendations(content_type: str, content_languages:List[str], genres:List[str], moods:List[str], releaseyear:str, minrating:str, otts:List[str], state: Annotated[dict, InjectedState]) -> str:
    """
    prepare a customised recommendation based on user's query. user's is prompt to certein questions and then a query is performed on the movie catalogue data. 

    Args:
        content_type - type of the content. Example content_type="M"
        content_language - Language of the content like Hindi, English etc. Example values of content_language = ["Hindi"]
        genre - Genre of the movie. Example values of the genre - ["Horror”]
        moods - Group of genre for a particular mood of the user. 
        releaseyear - release year of the content. is being categorised in "1", "2", "3", "4", "5". ("1" is for 2021-2024, "2" is for 2000-2020, "3" is for 1990-2000, "4" is for 1980-1989, "5" is for 1900-1979)
        minrating - rating of the movie
        otts - Looking for which ott platform. Example values - ["Netflix", "Amazon Prime Video"]
    """

    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(context_obj.company)
    
    arg_data = {
      "type":content_type,
      "languages": content_languages,
      "genres": genres,
      "moods": moods,
      "releaseyear": releaseyear,
      "minrating": minrating,
      "otts": otts
    }

    # print(context.extra_save_data["message_payload"])
    try : 
      api_auth_token = context_obj.extra_save_data.get("message_metadata", {}).get('api_auth_token', None)
      api_res = {}


      if api_auth_token:
        workflow_logger.add(f"Tool: prepare_movie_recommendations | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | advanced_movie_recommendation_api_auth arguments: {arg_data}")
        headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "Authorization": f"{api_auth_token}" if api_auth_token else "" 
            }
        api_res = BaseAgent(company=context_obj.company,agent_slug=f"api_agent.advanced_movie_recommendation_api_auth").invoke_agent(args=arg_data, ai_args={}, custom_headers = headers)
        workflow_logger.add(f"Tool: prepare_movie_recommendations | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | advanced_movie_recommendation_api_auth response: {api_res}")
      else :
        workflow_logger.add(f"Tool: prepare_movie_recommendations | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | advanced_movie_recommendation_api arguments: {arg_data}")
        api_res = BaseAgent(company=context_obj.company,agent_slug=f"api_agent.advanced_movie_recommendation_api").invoke_agent(args=arg_data, ai_args={}, custom_headers = {})
        workflow_logger.add(f"Tool: prepare_movie_recommendations | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | advanced_movie_recommendation_api response: {api_res}")
      
      if not api_res:
        return "Oops! No movie found, please try again."
      
      api_res = r"{}".format(json.dumps(api_res)).replace("\\", r"\\")
      return api_res
    
    except Exception as e:
       raise APIConnectionError()


@tool()
def find_similar_movies(content_name: str, find_similar:bool, state: Annotated[dict, InjectedState]) -> str:
    """
    Finds movie details or similar movies of a particular movie

    Args:
        content_name - name of the content of which the similar movies or web series needs to be found. Example value - "A few dollars more"
        find_similar - boolean field which indicated if user is looking for similar movie or he is just wants detail of the movie. Example value - True/False 
    """

    # context = state['workflow_context']
    context_obj = PipelineState.get_workflow_context_object_from_state(state)
    CompanyUtils.set_company_registry(context_obj.company)
    
    movie_search_arg_data = {
      "pagesize" : 1,
      "word": content_name
    }


    try : 
      
      api_auth_token = context_obj.extra_save_data.get("message_metadata", {}).get('api_auth_token', None)

      

      
      ## get movie by name
      if False and api_auth_token:
        headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "Authorization": f"{api_auth_token}" if api_auth_token else "" 
            }
        workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | movie_search_api_auth arguments: {movie_search_arg_data}")
        movie_details_res = BaseAgent(company=context_obj.company,agent_slug=f"api_agent.movie_search_api_auth").invoke_agent(args=movie_search_arg_data, ai_args={}, custom_headers=headers)
        workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | movie_search_api_auth response: {movie_details_res}")
      else :
        workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | movie_search_api arguments: {movie_search_arg_data}")
        movie_details_res = BaseAgent(company=context_obj.company,agent_slug=f"api_agent.movie_search_api").invoke_agent(args=movie_search_arg_data, ai_args={}, custom_headers = {})
        workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | movie_search_api response: {movie_details_res}")
    

      ## similar movies 
      if find_similar is True and movie_details_res is not None:
        similar_movies = {}
        similar_movie_arg_data = {
                                  "movieID" : movie_details_res[0].get("id", -1)
                                }
        
        if False and api_auth_token:
          headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "Authorization": f"{api_auth_token}" if api_auth_token else "" 
            }
          workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | find_similar_movie_api_auth arguments: {similar_movie_arg_data}")
          similar_movies = BaseAgent(company=context_obj.company,agent_slug=f"api_agent.find_similar_movie_api_auth").invoke_agent(args=similar_movie_arg_data, ai_args={}, custom_headers=headers )
          workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | find_similar_movie_api_auth response: {similar_movies}")
          similar_movies = r"{}".format(json.dumps(similar_movies)).replace("\\", r"\\")
          return similar_movies
        else :
          workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | find_similar_movie_api arguments: {similar_movie_arg_data}")
          similar_movies = BaseAgent(company=context_obj.company,agent_slug=f"api_agent.find_similar_movie_api").invoke_agent(args=similar_movie_arg_data, ai_args={}, custom_headers={})
          workflow_logger.add(f"Tool: find_similar_movies | Session: [{context_obj.session_id}] | Company: [{context_obj.company}] | find_similar_movie_api response: {similar_movies}")
          
          if not similar_movies:
            return "Oops! No movie found, please try again."
          
          similar_movies = r"{}".format(json.dumps(similar_movies)).replace("\\", r"\\")
          return similar_movies
    
      elif find_similar is True and movie_details_res is None:
        return "Oops! No movie found, please try again."
      
      elif find_similar is False:
        if movie_details_res:
          movie_details_res = r"{}".format(json.dumps(movie_details_res)).replace("\\", r"\\")
          return movie_details_res 
        else :
          return "Oops! No movie found, please try again."
      

    except Exception as e:
      raise APIConnectionError()
 
