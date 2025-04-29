from api_controller.models import ApiController
from chat.models import RequestMedium
from company.models import CompanySetting


class WhatsappMicrosServiceManager:

    @classmethod
    def get_micro_service_init_config(cls):
        config = {}
        cs_wn = ApiController.without_company_objects.filter(phone_number__isnull=False).select_related('company')
        """ Adding config to relevant company"""
        for _cs in cs_wn:
            config[_cs.phone_number] = {"company_id": _cs.company_id, "company_name": _cs.company.name}
            company_id = _cs.company_id
            wa_provider = _cs.auth_credentials if _cs.auth_credentials else {}
            wa_provider['provider'] = _cs.request_medium
            config[_cs.phone_number]["whatsapp_provider"] = wa_provider
            #for conf_key, conf_value in config.items():
            #    if company_id == conf_value.get("company_id"):
            #        config[conf_key]["whatsapp_provider"] = wa_provider

        return config
