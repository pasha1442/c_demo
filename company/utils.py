from api_controller.models import ApiController
from basics.utils import Registry
from backend.constants import CURRENT_API_COMPANY
from company.models import CompanySetting, Company
from asgiref.sync import sync_to_async

class CompanyUtils:

    @staticmethod
    def get_company_from_phone_number(phone_number):
        query_data = CompanySetting.without_company_objects.get(value=phone_number)
        stored_phone_number = query_data.value
        if phone_number == stored_phone_number:
            CompanyUtils.set_company_registry(query_data.company)
            return query_data.company
        return None
    
    @staticmethod
    def get_api_controller_from_phone_number(phone_number):
        api_controller = ApiController.without_company_objects.filter(
            phone_number=phone_number
        ).first()
        
        if api_controller:
            CompanyUtils.set_company_registry(api_controller.company)
            return api_controller
        
    @staticmethod
    def get_company_from_company_id(company_id):
        company = Company.objects.get(id=company_id)
        return company

    @staticmethod
    async def async_get_company_from_company_id(company_id):
        company = await sync_to_async(Company.objects.get)(id=company_id)
        return company

    @staticmethod
    def set_company_registry(company):
        reg = Registry()
        reg.set(CURRENT_API_COMPANY, company)

    @staticmethod
    def get_current_company_object():
        return Registry().get(CURRENT_API_COMPANY)
