from backend.services.kafka_service import BaseKafkaService
from basics.api.views import BaseModelViewSet
from django.contrib.auth import get_user_model
from basics.api import api_response_codes
from django.utils.translation import gettext_lazy as _
from basics.utils import check_mandatory_values
from chat.auth import ApiKeyAuthentication
from systemsetting.models import SystemSetting, DataProcessingQueue
from systemsetting.services.micro_service_managers.base_micro_service import BaseMicroServiceManager
from systemsetting.services.system_health_check_service import HealthCheckService

User = get_user_model()


class SystemSettingManager(BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]

    def get_config_over_key(self, request):
        request_data = request.data
        if request_data:
            _required_values = check_mandatory_values(request_data, ['config'])
            if _required_values:
                return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                             message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                             data=_required_values)

            else:
                _key = request_data.get('config', "")
                _config = SystemSetting.objects.filter(key=_key).first()
                return self.success_response(data={_config.key if _config else "key": _config.value if _config else ""},
                                             message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})


class MicroServiceConfigurationManager(BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]

    def get_micro_service_init_configurations(self, request):
        request_data = request.data
        if request_data:
            _required_values = check_mandatory_values(request_data, ['micro_services'])
            if _required_values:
                return self.failure_response(error_code=api_response_codes.ERROR_MISSING_REQUIRED_PARAMS,
                                             message=_(api_response_codes.MESSAGE_MISSING_REQUIRED_PARAMS),
                                             data=_required_values)

            else:
                micro_services = request_data.get("micro_services", [])
                _response = {}
                for micro_service in micro_services:
                    _response[micro_service] = BaseMicroServiceManager(micro_service).get_micro_service_init_config()
                return self.success_response(data=_response,
                                             message=api_response_codes.MESSAGE_REQUESTED_SUCCESSFULLY)
        return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                     message=_(api_response_codes.MESSAGE_INVALID_DATA), data={})


class DataProcessingQueueManager(BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]

    def get_queue_count(self, request):
        queue_name = request.GET.get('queue_name')
        failure_queue_name = BaseKafkaService(topic_name=queue_name).get_failure_queue_name(topic_name=queue_name)

        queue_count = BaseKafkaService(topic_name=queue_name).get_queue_count()
        failure_queue_count = BaseKafkaService(topic_name=failure_queue_name).get_queue_count()

        res = {"queue_count": queue_count, "queue_name": queue_name, "failure_queue_name": failure_queue_name,
               "failure_queue_count": failure_queue_count}

        return self.success_response(data={'success': True, 'queues': res},
                                     message="Queue count fetch successfully")

    def get_queue_list(self, request):
        try:
            # Query to fetch all active queues
            active_queues = DataProcessingQueue.objects.filter(is_active=True).values('id', 'name', 'queue_name')
            queue_list = list(active_queues)

            return self.success_response(data={'success': True, 'queues': queue_list},
                                         message="Queue list fetch successfully")

        except Exception as e:
            return self.failure_response(error_code=api_response_codes.ERROR_INVALID_DATA,
                                         data={'success': False, 'error': str(e)}, status_code=500)


class HealthStatusManager(BaseModelViewSet):
    authentication_classes = [ApiKeyAuthentication]

    def check_system_health(self, request):
        try:
            health_data = []

            # system_health = HealthCheckService().system_health_check()
            health_service_list = ['kafka', 'db', 'cache', 'redis', 'storage', 'migration', 'celery', 'url_health_checker',
                                   'system_services_health_checker']
            custom_health_status = HealthCheckService().get_health_check_status(health_service_list)
            health_data.append({"custom_health": custom_health_status})

            return self.success_response(data=health_data, message="Health status fetch successfully.")
        except Exception as e:
            return self.failure_response(message="Something went wrong", data={"error": str(e)},
                                         error_code=api_response_codes.MESSAGE_SOMETHING_WENT_WRONG)
