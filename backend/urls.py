"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path
from dash.views import *
from chat.views import *
from django.urls import path, include
import debug_toolbar
from django.conf.urls.static import static
from django.conf import settings


admin.site.site_header = 'CygnusAlpha'
admin.site.site_title = 'CygnusAlpha'
LOGIN_URL = "/admin/login/"

urlpatterns = [
    path('admin/defender/', include('defender.urls')), # defender admin
    path('admin/', admin.site.urls),
    path('api/v1/', include('backend.api_urls')),
    path('webhook/v1/', include('backend.webhook_urls')),
    # path('__debug__/', include(debug_toolbar.urls)),
    path('chat/', include('chat.urls')),
    path('', include('chat.urls')),

    # Url must be set as above URL
    path('api/register/', UserRegistrationAPIView.as_view(), name='user-registration'),
    path('api/login/', LoginAPIView.as_view(), name='login'),
    path('api/keys/', ApiKeyOperations.as_view(), name='list_api_keys'),
    path('api/keys/create/', ApiKeyOperations.as_view(), name='create_api_key'),
    path('api/keys/delete/<int:key_id>/', ApiKeyOperations.as_view(), name='delete_api_key'),
    path('api/chat/', ChatAPIView.as_view(), name='chat'),
    path('api/chat/agent', AgentChatAPIVIew.as_view(), name='chat'),
    path('api/chat/agent/', AgentChatAPIVIew.as_view(), name='chat'),
    path('api/chat/summary/', SummaryChatAPIVIew.as_view(), name='chat'),
    path('api/chat/summary', SummaryChatAPIVIew.as_view(), name='chat'),
    path('api/chat/actions/', ActionChatAPIVIew.as_view(), name='chat'),
    path('api/chat/actions', ActionChatAPIVIew.as_view(), name='chat'),
    path('api/chat/sentiments', SenAnalysisChatAPIVIew.as_view(), name='chat'),
    path('api/chat/sentiments/', SenAnalysisChatAPIVIew.as_view(), name='chat'),
    path('api/chat/profile/', ProfileUpdateChatAPIVIew.as_view(), name='chat'),
    path('api/chat/profile', ProfileUpdateChatAPIVIew.as_view(), name='chat'),
    path('api/chat/conversations/', ConversationHistoryAPIVIew.as_view(), name='chat'),
    path('api/chat/conversations', ConversationHistoryAPIVIew.as_view(), name='chat'),
    path('api/chat/agentprofile/', AgentProfileAPIVIew.as_view(), name='chat'),
    path('api/chat/agentprofile', AgentProfileAPIVIew.as_view(), name='chat'),
    path('api/geetashloka', GeetaSearchAPIVIew.as_view()),
    re_path(r'^gvi/search/(?P<chapter_no>\d+(\.\d+)?)/$', gvi_search_page, name='gvi_search_page_with_chapter'),
    path('gvi/chat/', gvi_chat_page, name='gvi_chat_page'),
    path('recobee/chat/', recobee_chat_page, name='recobee_chat_page'),
    path('recobee-api/chat/', recobee_api_chat_page, name='recobee_api_chat_page'),
    path('kindlife/chat/', kindlife_chat_page, name='kindlife_chat_page'),
    path('kindlife-bizz/chat/', kindlife_bizz_chat_page, name='kindlife_bizz_chat_page'),
    path('auriga/chat/', auriga_chat_page, name='auriga_chat_page'),
    path('stitch/chat/', stitch_chat_page, name='stitch_chat_page'),
    path('gvi/home/', gvi_home_page, name='gvi_home_page'),
    path('api/services/', ListServicesAPIView.as_view(), name='list_services'),
    path('api/services/my', UserServicesAPIView.as_view(), name='list_services'),
    path('api/client/services/', UpdateClientServicesAPIView.as_view(), name='update_client_services'),
    path('', include('chat.urls')),
    path('systemsetting/', include('systemsetting.urls')),
    path("google_sso/", include("django_google_sso.urls", namespace="django_google_sso")),
    path('page-builder/', include('insights.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]