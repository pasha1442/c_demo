from openmeter import Client
from cloudevents.http import CloudEvent
from cloudevents.conversion import to_dict
from decouple import config
from company.models import Company
from metering.services.session_service import SessionManager
from api_controller.models import ApiController
from datetime import datetime, timedelta
from metering.services.kafka.metering_kafka_producer_service import MeteringKafkaProducer
from basics.utils import UUID
import asyncio

class OpenMeter:

    def __init__(self, company=None, api_controller=None, session_id=None, request_args={}):
        """ Event Types """
        self.et_api_call = "api_call"
        self.et_llm_call = "llm_chat"
        self.et_vector_db_call = "vector_db_call"
        self.et_app_log = "app_log"
        self.et_db_ingest = "db_ingest"
        self.et_webhook = "webhook"
        self.et_socket = "socket"
        self.et_rpc = "rpc"
        self.goal_completion = "goal_completion"
        self.goal_failure = "goal_failure"

        """ Dynamic Variables"""
        self.company = company
        self.api_controller = api_controller
        self._client, self.om_secret_key = self.get_openmeter_connection_obj()

        self.request_id = request_args.get("request_id") if request_args.get("request_id") else self.get_request_id()
        self.session_id = request_args.get("session_id", "")
        self.request_session_id = request_args.get("session_id", "")
        self.set_billing_session(request_args.get('message', {}).get("text", ""))

    def get_openmeter_connection_obj(self, secret_key=None):
        _host = config('OPEN_METER_HOST', default="")
        _secret_key = config('OPEN_METER_SECRET_KEY', default="")
        if secret_key:
            om_secret_key=secret_key
            client = Client(endpoint=_host,
                            headers={"Accept": "application/json",
                                     "Authorization": f"Bearer {secret_key}", }, )
        else:
            if self.company.openmeter_secret_key:
                om_secret_key = self.company.openmeter_secret_key
                client = Client(endpoint=_host,
                              headers={"Accept": "application/json",
                                       "Authorization": f"Bearer {self.company.openmeter_secret_key}", }, )
            else:
                om_secret_key = _secret_key
                client = Client(endpoint=_host,
                              headers={"Accept": "application/json",
                                       "Authorization": f"Bearer {_secret_key}", }, )
        return client, om_secret_key

    def get_event_id(self):
        return f"{UUID.get_uuid()}-{self.billing_session_id}"

    def get_request_id(self):
        return f"{UUID.get_uuid()}"

    def ingest_vector_db_call(self, args):
        attributes = {
            "id": self.get_event_id(),
            "type": self.et_vector_db_call,
            "source": self.api_controller.name,
            "subject": self.company.current_env
        }
        vector_db__data = {
            "request_id": f"{self.request_id}",
            "session_id": f"{self.session_id}",
            "billing_session_id": f"{self.billing_session_id}",
            "service": self.api_controller.name,
            "source": self.api_controller.name,
            "application_type": self.api_controller.application_type,
            "request_medium": self.api_controller.request_medium,
            "database": args.get("database", ""),
            "database_type": args.get("database_type", ""),
            "agent": args.get("agent", ""),
            "data_source": args.get("data_source", ""),
            "version": 4
        }
        self.push_event(attributes=attributes, data=vector_db__data)

    def ingest_goal_failure(self, goal="", error=""):
        attributes = {
            "id": self.get_event_id(),
            "type": self.goal_failure,
            "source": self.api_controller.name,
            "subject": self.company.current_env
        }
        data = {
            "request_id": f"{self.request_id}",
            "session_id": f"{self.session_id}",
            "billing_session_id": f"{self.billing_session_id}",
            "service": self.api_controller.name,
            "source": self.api_controller.name,
            "application_type": self.api_controller.application_type,
            "request_medium": self.api_controller.request_medium,
            "goal": goal,
            "error": error,
        }
        self.push_event(attributes=attributes, data=data)

    def ingest_goal_completion(self, goal="", reference_id=""):
        attributes = {
            "id": self.get_event_id(),
            "type": self.goal_completion,
            "source": self.api_controller.name,
            "subject": self.company.current_env
        }
        data = {
            "request_id": f"{self.request_id}",
            "session_id": f"{self.session_id}",
            "billing_session_id": f"{self.billing_session_id}",
            "service": self.api_controller.name,
            "source": self.api_controller.name,
            "application_type": self.api_controller.application_type,
            "request_medium": self.api_controller.request_medium,
            "goal": goal,
            "reference_id": reference_id,
        }
        self.push_event(attributes=attributes, data=data)

    def ingest_api_call(self, api_method=""):
        attributes = {
            "id": self.get_event_id(),
            "type": self.et_api_call,
            "source": self.api_controller.name,
            "subject": self.company.current_env
        }
        data = {
            "request_id": f"{self.request_id}",
            "session_id": f"{self.session_id}",
            "billing_session_id": f"{self.billing_session_id}",
            "service": self.api_controller.name,
            "source": self.api_controller.name,
            "application_type": self.api_controller.application_type,
            "request_medium": self.api_controller.request_medium,
            "api_method": api_method,
            "endpoint": ""
        }
        self.push_event(attributes=attributes, data=data)

    def ingest_llm_call(self, args):
        attributes = {
            "id": self.get_event_id(),
            "type": self.et_llm_call,
            "source": self.api_controller.name,
            "subject": self.company.current_env
        }
        llm_data = {
            "request_id": f"{self.request_id}",
            "session_id": f"{self.session_id}",
            "billing_session_id": f"{self.billing_session_id}",
            "service": self.api_controller.name,
            "source": self.api_controller.name,
            "application_type": self.api_controller.application_type,
            "request_medium": self.api_controller.request_medium,
            "model_company": args.get("llm", ""),
            "model": args.get("model", ""),
            "agent": args.get("agent", ""),
            "data_source": args.get("data_source", ""),
            "version": 4,
            "token_count": args.get("total_token", 0),
            "input_token_count": args.get("input_token", 0),
            "output_token_count": args.get("output_token", 0)
        }
        self.push_event(attributes=attributes, data=llm_data)

    def set_billing_session(self, content):
        _session_type = self.api_controller.billing_session_type if self.api_controller else ApiController.BILLING_SESSION_TYPE_PER_CALL_ONE_SESSION
        self.session_id, self.billing_session_id = SessionManager(company=self.company).generate_session(
            session_type=_session_type,
            api_controller=self.api_controller,
            session_id=self.session_id,
            content=content)

    def query(self):
        time_to = self.round_to_minute(datetime.utcnow()).isoformat() + "Z"  # Current time in ISO 8601 format
        time_from = self.round_to_minute(datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z"
        _res = self._client.query_meter(
            meter_id_or_slug=self.et_api_call,
            filter_group_by={"session_id": self.request_session_id},
            from_parameter=time_from,
            to=time_to
            # limit=1,
            # sort="desc"
        )
        _res_data = _res.get("data", [])
        return _res_data[0].get('value', 0) if len(_res_data) > 0 else 0

    def push_event(self, attributes={}, data={}):
        _payload = {"attributes": attributes, "event_data": data, "company_id": self.company.id,
                    "om_secret_key": self.om_secret_key}
        asyncio.run(MeteringKafkaProducer().push_openmeter_raw_data_in_kafka(_payload))

        # _timestamp = datetime.now().timestamp()
        # event = CloudEvent(
        #     attributes=attributes,
        #     data=data,
        # )
        # self._client.ingest_events(to_dict(event))

    def publish_event_to_openmeter(self, _payload):
        attributes = _payload.get("attributes", {})
        data = _payload.get("event_data", {})
        om_secret_key = _payload.get("om_secret_key", {})
        _timestamp = datetime.now().timestamp()
        event = CloudEvent(
             attributes=attributes,
             data=data,
        )
        _client, _ = self.get_openmeter_connection_obj(om_secret_key)
        _client.ingest_events(to_dict(event))


    def to_dict(self):
        """Convert OpenMeter instance to a serializable dictionary."""
        return {
            "event_types": {
                "api_call": self.et_api_call,
                "llm_call": self.et_llm_call,
                "vector_db_call": self.et_vector_db_call,
                "app_log": self.et_app_log,
                "db_ingest": self.et_db_ingest,
                "webhook": self.et_webhook,
                "socket": self.et_socket,
                "rpc": self.et_rpc,
                "goal_completion": self.goal_completion,
                "goal_failure": self.goal_failure
            },
            "request_info": {
                "request_id": self.request_id,
                "session_id": self.session_id,
                "request_session_id": self.request_session_id,
                "billing_session_id": getattr(self, 'billing_session_id', None)
            },
            "company_id": self.company.id if self.company else None,
            "api_controller": (
                self.api_controller.to_dict() if self.api_controller else None
            )
        }
    
    @classmethod
    def from_dict(cls, data, company_obj: Company = None):
        """
        Rebuilds an OpenMeter object from the dictionary produced by `to_dict()`.
        If needed, you can pass in the restored Company object so that
        OpenMeter.__init__ can link them up.
        """

        request_info = data.get("request_info", {})
        request_id = request_info.get("request_id")
        session_id = request_info.get("session_id")

        api_controller_data = data.get("api_controller")
        if api_controller_data:
            api_controller_obj = ApiController.from_dict(api_controller_data)
        else:
            api_controller_obj = None

        om = cls(
            company=company_obj,
            api_controller=api_controller_obj,
            session_id=request_info.get("session_id"),
            request_args={"request_id": request_info.get("request_id")}
        )
        om.billing_session_id = request_info.get("billing_session_id")

        return om


    """
        await c.query_meter(meter_id_or_slug="api_requests_total",group_by=["method"],)
        await c.query_meter(meter_id_or_slug="api_requests_total",filter_group_by={"method": "GET"},)
        
        Payload Decided for Openmeter
        {
            "session_id": f"{self.session_id}",
            "service": self.api_controller.name,
            "source": self.api_controller.name,
            "application_type": "backend",
            "request_medium": "whatapp",
            "model_company": "open_ai",
            "model": "GPT",
            "version": 4,  # 4o
            "api_method": "search_info",
            "endpoint": " ",
            "token_count": "",
            "input_token_count": "",
            "output_token_count": "",
        }
        
        {
          "session_id":""
          "service": knowledge_ai, order_info, ticketing
          "source": "prod_API",
          "application_type": "frontend/backend/batch_processing"
          "request_medium": api/ whatapp/sdk/
          "model_company": open_ai, gemini, mistral, microsoft, facebook
          "model": gpt/lama/
          "version": 1.0
          "api_method": knowledge_ai, order_detail, shipping_info
          "endpoint": " "
          "token_count": ""
          "input_token_count":  ""
          "output_token_count": ""
        }
    """
