from chat.models import Conversations
from chat.serializers import ConversationSerializer


class PersistentChatHistoryService:
    def __init__(self):
        pass
        
    def fetch_conversation_by_client_identifier(self, client_identifier, limit=14, start_from_hello=False):
        chat_history = Conversations.objects.filter(client_identifier=client_identifier).order_by('-created_at')[:limit]
        if start_from_hello:
            latest_hello_index = None
            for index, conversation in enumerate(chat_history):
                if conversation.role == 'user' and any(greeting in conversation.message.lower() for greeting in ['hello']):
                    latest_hello_index = index
                    break

            if latest_hello_index is not None and latest_hello_index < limit:
                filtered_conversations = chat_history[:latest_hello_index + 1]
            else:
                filtered_conversations = chat_history
        else:
            filtered_conversations = chat_history
        
        final_conversation = []

        for conversation in filtered_conversations:
            final_conversation.append(conversation)

        serializer = ConversationSerializer(final_conversation, many=True)
        req_chat_history = serializer.data

        custom_data = []
        for item in req_chat_history:
            entry = {'role': item['role'], 'content': item['message']}
            if 'function_name' in item and item['function_name']:
                entry['name'] = item['function_name']
            custom_data.append(entry)

        return custom_data