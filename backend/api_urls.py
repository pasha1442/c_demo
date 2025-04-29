from django.urls import path, include

urlpatterns = [
    path('auth/', include('auth.api.urls')),
    path('chat/', include('chat.api.urls')),
    path('api-controller/', include('api_controller.api.urls')),
    path('system-settings/', include('systemsetting.api.urls')),
    path('notifications/', include('notifications.api.urls')),
    path('data-processing/', include('data_processing.api.urls')),
    path('insights/', include('insights.urls')),
   #  path('user-guide/', include('user_guide.api.urls')),
]