from chat.clients.workflows.trcapital import customer_support_workflow
from company.models import Company
from metering.services.openmeter import OpenMeter


def run_workflow(
    initial_message: str, 
    mobile_number: str, 
    session_id: str, 
    client_identifier: str,
    company: Company, 
    openmeter_obj: OpenMeter, 
    message_data:dict, 
    whatsapp_provider):

    output = customer_support_workflow.run_workflow(
        initial_message=initial_message,
        mobile_number=mobile_number,
        session_id=session_id,
        client_identifier=client_identifier,
        company=company,
        openmeter_obj=openmeter_obj, 
        message_data=message_data, 
        whatsapp_provider=whatsapp_provider)

    return output