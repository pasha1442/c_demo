import json
from backend.constants import CURRENT_API_COMPANY
from basics.utils import Registry
from chat.models import WorkflowAttributes


class WorkflowAttributeService:
    
    def __init__(self, company = None):
        self.company = company
        if company:
            Registry().set(CURRENT_API_COMPANY, company)
    
    def get_workflow_attributes(self, attribute_type):
        formatters = WorkflowAttributes.objects.filter(attribute_type=attribute_type).values('id', 'name', 'response_formatter_type', 'content')
        
        return formatters
    
    def get_workflow_attribute_by_name(self, name):
        formatter = WorkflowAttributes.objects.filter(name=name).values('response_formatter_type', 'content')
        
        return formatter
    
    def save_workflow_attribute(self, name, attribute_type, content, response_formatter_type=None):
        if attribute_type == WorkflowAttributes.ATTRIBUTE_TYPE_RESPONSE_FORMATTER_CHOICE:
            if not response_formatter_type:
                raise ValueError("Response Formatter Type is required for Response Formatter Attribute Type")
            
            self.save_response_formatter(name, attribute_type, content, response_formatter_type)
            
                
    def save_response_formatter(self, name, attribute_type, content, response_formatter_type):
        if response_formatter_type == WorkflowAttributes.RESPONSE_FORMATTER_TYPE_JSON:
            try:
                
                workflow_attr, created = WorkflowAttributes.objects.update_or_create(
                    name=name,
                    defaults={
                        "attribute_type": attribute_type,
                        "content": content,
                        "is_active": True,
                        "response_formatter_type": response_formatter_type
                    }
                )

                if created:
                    print("New WorkflowAttributes created!")
                else:
                    print("Existing WorkflowAttributes updated!")
                    
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON content for Response Formatter Type JSON")
            