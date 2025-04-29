from systemsetting.services.micro_service_managers.whatsapp_micro_service import WhatsappMicrosServiceManager


class BaseMicroServiceManager:

    def __init__(self, micro_service_slug=None):
        micro_services = {"whatsapp": WhatsappMicrosServiceManager}
        self.micro_service = micro_services.get(micro_service_slug, None)()

    def get_micro_service_init_config(self):
        config = self.micro_service.get_micro_service_init_config()
        return config if config else {}