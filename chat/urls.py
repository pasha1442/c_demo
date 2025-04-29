from django.urls import path
from basics.admin import wrap_admin_view
from .views import GviGraphView, QdegreeGraphView, index, chatbot_api, ChatView, GeetaGraphView, omf_contact_us_page, GraphWorkView, ConversationHistory, recobee_multimodel_chat_page


urlpatterns = [
    # index page chat window '' >> 'chat-dashboard'
    path('', index, name='index'),
    path('api/chatbot/', chatbot_api, name='chatbot_api'),
    path('chat-window/', wrap_admin_view(ChatView.as_view()), name='chat_view'),
    path('conversation-history/', wrap_admin_view(ConversationHistory.as_view()), name='conversation_history'),

    path('graph-workflow/', wrap_admin_view(GraphWorkView.as_view()), name='chat_view'),
    path('api/chat/gvi/explore', GviGraphView.as_view(), name='gvi_chatbot'),
    path('api/chat/qdegree/survey',  QdegreeGraphView.as_view(), name='qdegree_chatbot'),
    path('api/chat/geeta/explore',  GeetaGraphView.as_view(), name='geeta_chatbot'),
    path('omf/contact_us/', omf_contact_us_page, name='omf_contact_us'),
    path('multimodeltest/chat/', recobee_multimodel_chat_page, name="recobee_multimodel_chat_page")
]
