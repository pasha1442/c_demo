from django.urls import path

from basics.admin import wrap_admin_view
from systemsetting.views import HealthStatus

urlpatterns = [
    path('health-status', wrap_admin_view(HealthStatus.as_view()), name='health_status'),
    ]