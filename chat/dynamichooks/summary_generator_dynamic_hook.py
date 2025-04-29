from api_controller.models import ApiController
from chat.dynamichooks.base_dynamic_hooks import BaseDynamicHooks
from chat.services.conversation_manager_service import ConversationManagerService
from asgiref.sync import sync_to_async

class SummaryGeneratorDynamicHook(BaseDynamicHooks):
    
    async def execute(self, company, state):
        await self.generate_summary(company, state)
    
    async def process(self, company, state):
        # await self.generate_summary(company, state)
        await self.execute(company, state)
        
    async def generate_summary(self, company, state):
        if state.get('session_id'):
            if state.get('api_route'):
                api_controller = await sync_to_async(ApiController.without_company_objects.get)(
                    api_route=state.get('api_route'), company=company
                )
                summary_generator = ConversationManagerService(company=company, api_controller=api_controller)
            else:
                summary_generator = ConversationManagerService(company=company)
            
            await summary_generator.generate_summary(
                company=company, 
                client_identifier=state.get("client_identifier"), 
                mobile=state.get("customer_mobile"), 
                extra_save_data={"session_id": state.get('session_id')}
            )    