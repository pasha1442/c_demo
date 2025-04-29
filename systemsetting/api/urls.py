from django.urls import path

from basics.admin import wrap_admin_view
from systemsetting.api import views
from systemsetting.api.views import SystemSettingManager, MicroServiceConfigurationManager, DataProcessingQueueManager, \
    HealthStatusManager

urlpatterns = [
    path('get-config-over-key', SystemSettingManager.as_view({"post": "get_config_over_key"})),
    path('get-micro-service-init-configurations', MicroServiceConfigurationManager.as_view({"post": "get_micro_service_init_configurations"})),
    path('get-queue-count', DataProcessingQueueManager.as_view({"get": "get_queue_count"}), name='get_queue_count'),
    path('get-queue-list', DataProcessingQueueManager.as_view({"get": "get_queue_list"}), name='get_queue_list'),
    path('system-health-status', HealthStatusManager.as_view({"get": "check_system_health"}), name='system_health_status'),


]
