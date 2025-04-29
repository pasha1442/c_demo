from django.urls import path
from api_controller.api.views import APIControllerManager, APIRouterManager, ExternalAPIControllerManager

urlpatterns = [
    path('invoke-service/<str:api_route>/', APIRouterManager.as_view({"post": "execute_workflow_over_route"})),
    path('api-controller/get-available-routes/', APIControllerManager.as_view({"post": "get_available_routes"})),
    path('api-controller/update-graph-json/', APIControllerManager.as_view({"post": "update_graph_json"})),
    path('api-controller/get-graph-json-over-route/', APIControllerManager.as_view({"post": "get_graph_json_over_route"})),
    path('api-controller/get-help-window-content/', APIControllerManager.as_view({"get": "get_help_window_content"}), name="get_help_window_content"),
    path('api-controller/get-company-wise-voice-assistant-workflows/', ExternalAPIControllerManager.as_view({"get": "get_company_wise_voice_assistant_workflows"}), name="get_company_wise_voice_assistant_workflows"),

]
