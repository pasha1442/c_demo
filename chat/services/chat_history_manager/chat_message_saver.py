from asgiref.sync import sync_to_async
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from chat import utils
from basics.utils import Registry
from backend.constants import CURRENT_API_COMPANY


class ChatMessageSaverService:
    def __init__(self, company=None, api_controller=None, chat_manager = None):
        self.company = company if company else Registry().get(CURRENT_API_COMPANY)
        if chat_manager:
            self.chat_manager = chat_manager
        else:
            self.chat_manager = InMemoryChatHistoryService(company=company, api_controller=api_controller)

    async def save_message(
            self,
            company,
            role,
            mobile_number,
            message,
            extra_save_data,
            client_identifier,
            message_metadata={},
            return_instance=False,
            session_validated=False,
            api_controller=None
    ):
      
        """
        Save chat history to in-memory cache and persist to database.
        """
        from chat.services.conversation_manager_service import ConversationManagerService
        await sync_to_async(ConversationManagerService(company=company).validate_conversation_session)(**{**extra_save_data, "api_controller": api_controller})
        # Save to in-memory cache
        await self.chat_manager.save_chat_history(
            company=company,
            role=role,
            mobile=mobile_number,
            text=message,
            extra_save_data=extra_save_data,
            client_identifier=client_identifier,
            message_metadata=message_metadata,
            session_validated=session_validated
        )

        # Save to the database
        result = await sync_to_async(utils.save_conversation)(
            company=company,
            role=role,
            mobile=mobile_number,
            text=message,
            message_metadata=message_metadata,
            extra=extra_save_data,
            return_instance=return_instance,
        )

        if return_instance:
            return result
        return None
