from chat.clients.workflows.workflow_runner import WorkflowRunner
from chat.clients.workflows.icici import actionables_workflow, agent_assistant_workflow, agent_suggestions_workflow, customer_profile_update_workflow, evaluate_agent_workflow, sentiment_analysis_worflow, summary_workflow
from chat.clients.workflows.omf import ai_suggestions_workflow, borrower_history_workflow, omf_contact_us_workflow, omf_ticket_classifier_workflow
from basics.custom_exception import CompanyNotFoundException, LangfuseConnectionException, PromptNotFoundException, WorkflowCreationException, WorkflowExecutorException, APIConnectionError
from basics.custom_exception import WhyHowAIConnectionError, WhyHowAIDataRetrievalError, Neo4jConnectionError, Neo4jDataRetrievalError, PineconeConnectionError, PineconeDataRetrievalError, SQLDBConnectionError, SQLDataRetrievalError
import chat.utils as chat_utils
from metering.services.openmeter import OpenMeter
from langfuse.decorators import langfuse_context, observe
from chat.demo.voice_assistant.utils import initiate_call
from decouple import config

import traceback

from backend.logger import Logger


workflow_logger = Logger(Logger.WORKFLOW_LOG)
error_logger = Logger(Logger.ERROR_LOG)
import time
from asgiref.sync import sync_to_async
from backend.settings import LANGFUSE_CURRENT_ENVIRONMENT


class Workflow:

    def __init__(self, company=None, api_controller=None, request_args={}):
        self.company = company
        self.api_controller = api_controller
        self.request_args = request_args

        TRACING_ENABLED = config('ENABLE_LANGFUSE_TRACING', default=False, cast=bool)
        langfuse_context.configure(
            secret_key=company.langfuse_secret_key,
            public_key=company.langfuse_public_key,
            enabled=TRACING_ENABLED
        )

    @observe()
    async def init_workflow(self, route):
        try:
            response = {}
            openmeter_obj = OpenMeter(company=self.company, api_controller=self.api_controller,
                                      request_args=self.request_args)
            session_id = self.request_args.get('session_id', '')
            client_identifier = self.request_args.get('client_identifier') or self.request_args['mobile_number']
            langfuse_context.update_current_trace(user_id=self.request_args['mobile_number'], session_id=session_id,
                                                  name=route, tags=[LANGFUSE_CURRENT_ENVIRONMENT])

            if route == 'initiate-call':
                response = await sync_to_async(initiate_call)(self.company.id, self.request_args['mobile_number'], session_id, metadata=self.request_args['message']['metadata'])
                yield response

            # qdegree
            elif route == "survey":
                response = await sync_to_async(chat_utils.handle_webhook_message)(
                    self.company, None, self.request_args, '1.0', openmeter_obj
                )
                openmeter_obj.ingest_api_call(api_method="handle_webhook_message")

            # icici
            elif route == "agent-ai-suggestions":
                response = await sync_to_async(agent_suggestions_workflow.run_workflow)(
                    initial_message=self.request_args['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    company=self.company,
                    client_identifier=client_identifier,
                    openmeter_obj=openmeter_obj
                )
                yield response
                openmeter_obj.ingest_api_call(api_method="icici_run_agent_ai_suggestions_workflow")
            elif route == "agent-assistant":
                response = await sync_to_async(agent_assistant_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj,
                    conversation=self.request_args.get('conversation',"")
                )
                response = ', '.join(response)

                yield response
                openmeter_obj.ingest_api_call(api_method="icici_run_agent_assistant_workflow")
            elif route == "conversation-summary":
                response = await sync_to_async(summary_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                response = ', '.join(response)

                yield response
                openmeter_obj.ingest_api_call(api_method="icici_run_conversation_summary_workflow")
            elif route == "fetch-conversation-history":
                response = await sync_to_async(summary_workflow.get_conversation_history)(
                    mobile=self.request_args['mobile_number']
                )
                yield response
            elif route == "sentimental-analysis":
                response = await sync_to_async(sentiment_analysis_worflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                yield response[0]
                openmeter_obj.ingest_api_call(api_method="icici_run_semantic_analysis_workflow")
            elif route == "post-call-actionables":
                response = await sync_to_async(actionables_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                yield response[0]
                openmeter_obj.ingest_api_call(api_method="icici_run_actionables_workflow")
            elif route == "agent-evaluator":
                response = await sync_to_async(evaluate_agent_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                yield response
                openmeter_obj.ingest_api_call(api_method="icici_run_agent_evaluator_workflow")
            elif route == "agent_profile_data":
                response = await sync_to_async(evaluate_agent_workflow.get_agent_profile_data)(
                    agent_reference_id=self.request_args['mobile_number']
                )
            elif route == "customer-profile-update":
                response = await sync_to_async(customer_profile_update_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                yield response
                openmeter_obj.ingest_api_call(api_method="icici_run_customer_profile_update_workflow")
            elif route == "customer-profile-update-manual":
                response = await sync_to_async(customer_profile_update_workflow.save_customer_profile_manual)(
                    profile_data=self.request_args['profile_data'],
                    mobile_number=self.request_args['mobile_number']
                )
                yield response
            elif route == "get_customer_profile":
                response = await sync_to_async(customer_profile_update_workflow.get_customer_profile)(
                    mobile_number=self.request_args['mobile_number']
                )
                yield response
            # omf
            elif route == "ivr-ai-suggestions":
                response = await sync_to_async(ai_suggestions_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                yield response
                openmeter_obj.ingest_api_call(api_method="omf_run_ivr_ai_suggestions_workflow")
            elif route == "borrower-history":
                response = await sync_to_async(borrower_history_workflow.run_workflow)(
                    initial_message=self.request_args.get('message').get('text'),
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                openmeter_obj.ingest_api_call(api_method="omf_run_borrower_history_workflow")
            elif route == "omf-contact-us-chat":
                response = await sync_to_async(omf_contact_us_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                openmeter_obj.ingest_api_call(api_method="omf_run_contact_us_chat_workflow")
            elif route == "omf-ticket-classifier":
                response = await sync_to_async(omf_ticket_classifier_workflow.run_workflow)(
                    initial_message=self.request_args['message']['text'],
                    mobile_number=self.request_args['mobile_number'],
                    session_id=session_id,
                    client_identifier=client_identifier,
                    company=self.company,
                    openmeter_obj=openmeter_obj
                )
                openmeter_obj.ingest_api_call(api_method="omf_run_ticket_classifier_workflow")

            else:
                workflow_name = self.company.name + "_" + route
                workflow_json = self.api_controller.graph_json
                workflow_type = self.api_controller.workflow_type
                workflow_stream = self.api_controller.workflow_stream
                print(f"workflow type: {workflow_type}, workflow_stream: {workflow_stream}")
                workflow_obj = WorkflowRunner()
                message_data = self.request_args.get("message", {})
                media = self.request_args.get("message", {}).get("media", [])

                if isinstance(media, list) and len(media) > 0:
                    media_urls = [media_item.get("image_url", '') for media_item in media]
                    message_data['message_metadata'] = {'media_url': media_urls}
                else:
                    message_data['message_metadata'] = {'media_url': None}
                

                async for chunk in workflow_obj.run_workflow(workflow_name, workflow_json, workflow_type,
                                                             workflow_stream,
                                                             initial_message=self.request_args['message']['text'],
                                                             mobile_number=self.request_args['mobile_number'],
                                                             client_session_id=self.request_args['client_session_id'],
                                                             session_id=session_id, client_identifier=client_identifier,
                                                             company=self.company, openmeter_obj=openmeter_obj,
                                                             message_data=message_data,
                                                             message_payload=self.request_args,
                                                             save_ai_message=self.request_args.get('save_ai_message', True)):
                    yield chunk
                api_method_name = f"{self.company.name.lower()}_{route.replace('-', '_')}_workflow"
                openmeter_obj.ingest_api_call(api_method=api_method_name)

            print("- company", self.company, session_id)
            print("- response", response)
            workflow_logger.add(f"Response: {response}")
            # yield response 
        except WorkflowCreationException as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)
        except WorkflowExecutorException as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)
        except LangfuseConnectionException as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)
        except PromptNotFoundException as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)
        except CompanyNotFoundException as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except WhyHowAIConnectionError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except WhyHowAIDataRetrievalError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except PineconeConnectionError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except PineconeDataRetrievalError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except Neo4jConnectionError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except Neo4jDataRetrievalError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except SQLDBConnectionError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except SQLDataRetrievalError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)
            
        except APIConnectionError as e:
            error_logger.add(f"Error: {e}")
            print("Error: ", e)

        except Exception as e:
            error_logger.add(f"Error: {traceback.print_exc()}")
            print("Error: ", e)
        # yield "Some error occured. Please try again!"


"""
    Flow
    json
     @tool
      - declare "prompt/agent name"

    Company: q_degree_12
    - tool
      - get_prompt_name
             - langguse (q_degree_12)
                 - get agent ("prompt" / "Internal API Agent")
                   - execute
                       - prompt 
"""
