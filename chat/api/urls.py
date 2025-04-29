from django.urls import path
from chat.api.views import ChatBot, PromptManager, VoiceAssistantManager
from chat.api.views import ChatBot, PromptManager, InternalConversationManager, ExternalConversationManager, WorkflowStatusManager


urlpatterns = [
    path('chat/send-message', ChatBot.as_view({"post": "send_message"})),
    path('chat/get-active-prompts', PromptManager.as_view({"get": "get_active_prompts"})),

    path('voice-assistant/process-user-call/', VoiceAssistantManager.as_view({"post": "process_user_call"})),
    path('voice-assistant/get-call-status', VoiceAssistantManager.as_view({"get": "get_call_status"})),
    path('voice-assistant/voice-call-status-callback', VoiceAssistantManager.as_view({"post": "voice_call_status_callback"})),

    path('conversations/get-conversation-over-client-identifier', InternalConversationManager.as_view({"post": "get_conversation_over_client_identifier"})),
    path('conversations/get-all-recent-sessions-list', InternalConversationManager.as_view({"post": "get_all_recent_sessions_list"})),
    path('conversations/save-workflow-attribute', InternalConversationManager.as_view({"post": "save_workflow_attribute"})),
    path('conversations/get-workflow-attributes', InternalConversationManager.as_view({"get": "get_workflow_attribute"})),

    path('conversations/get-session-conversation-over-client-identifier', ExternalConversationManager.as_view({"post": "get_conversation_over_client_identifier"})),
    path('conversations/get-recent-sessions-list', ExternalConversationManager.as_view({"post": "get_recent_sessions_list"})),
    path('conversations/get-summary-over-session-id', ExternalConversationManager.as_view({"post": "get_summary_over_session_id"})),
    path('conversations/update-client-identifier-over-client-session-id',
         ExternalConversationManager.as_view({"post": "update_client_identifier_over_client_session_id"})),

    path('workflow/get-workflow-status-over-request-id',
         WorkflowStatusManager.as_view({"post": "get_workflow_status_over_request_id"})),
    path('workflow/verify-workflow-status-as-completed-over-request-id',
         WorkflowStatusManager.as_view({"post": "verify_workflow_status_as_completed_over_request_id"})),



]