import contextvars
from dataclasses import dataclass
from typing import Dict

from company.models import Company
from metering.services.openmeter import OpenMeter

@dataclass
class WorkflowState:
    mobile: str
    session_id: str
    company: Company
    openmeter: OpenMeter
    extra_save_data: Dict[str, str]
    message_payload: Dict



class WorkflowContext:
    
    def __init__(self, mobile, session_id, company, openmeter, extra_save_data, message_payload):
        self.mobile = mobile
        self.session_id = session_id
        self.company = company
        self.openmeter = openmeter
        self.extra_save_data = extra_save_data
        self.message_payload = message_payload
        self.interrupt_state = None
    
    # def set_context(self, context: WorkflowState):
    #     self.workflow_context.set(context)

    # def get_context(self) -> WorkflowState:
    #     return self.workflow_context.get()    
    
    def get_company_from_context(self):
        return self.company
    
    def to_dict(self):
        """Convert WorkflowContext into a serializable dictionary."""
        context_dict = {
            "mobile": self.mobile,
            "session_id": self.session_id,
            "company": self.company.to_dict() if self.company else None,
            "openmeter": self.openmeter.to_dict() if self.openmeter else None,
            "extra_save_data": self.extra_save_data,
            "message_payload": self.message_payload,
        }
            
        return context_dict

    @classmethod
    def from_dict(cls, data):
        """Rebuild a WorkflowContext from a dictionary."""
        company_data = data.get("company")
        if company_data:
            # pure Python object, not hitting the DB
            company_obj = Company.from_dict(company_data)
            # actual DB object
            #   company_obj = Company.objects.get(id=company_data["id"])
        else:
            company_obj = None

        openmeter_data = data.get("openmeter")
        if openmeter_data:
            openmeter_obj = OpenMeter.from_dict(data=openmeter_data, company_obj=company_obj)
        else:
            openmeter_obj = None
        return cls(
            mobile=data.get("mobile"),
            session_id=data.get("session_id"),
            company=company_obj,
            openmeter=openmeter_obj,
            extra_save_data=data.get("extra_save_data"),
            message_payload=data.get("message_payload"),
        )
