from chat.dynamichooks.base_dynamic_hooks import BaseDynamicHooks
import aiohttp
import json
import logging
from chat.dynamichooks.global_state_manager import GlobalCompanyStateManager

logger = logging.getLogger(__name__)

state_manager = GlobalCompanyStateManager()

class SnoopingOutgoingMsgHook(BaseDynamicHooks):
    
    async def execute(self, company, state):
        
        logger.info(f"Processing outgoing message hook for {state.get('client_identifier')}")
        
        webhook_url = self._get_webhook_url(company, 'snooping_outgoing_webhook_url')
        if not webhook_url:
            logger.warning(f"No outgoing webhook URL configured for company {company.id}")
            return
            
        message_data = {
            "company_id": str(company.id),
            "session_id": state.get("session_id"),
            "recipient": state.get("client_identifier"),
            "message": state.get("message", ""),
            "message_id": state.get("message_id", ""),
            "timestamp": state.get("timestamp", ""),
            "direction": "outgoing",
            "message_type": state.get("message_type", "text"),
            "media_url": state.get("media_url", "")
        }
        
        await self._forward_to_webhook(webhook_url, message_data)
    
    def _get_webhook_url(self, company, webhook_key):
        
        company_id = str(company.id)
        company_state = state_manager.get_company_state(company_id)
        
        if company_state and 'webhook_config' in company_state:
            return company_state.get('webhook_config', {}).get(webhook_key)
        
        # Fallback to company object if not in state manager
        if hasattr(company, 'webhook_config'):
            config = company.webhook_config
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                    # Update state manager for future use
                    state_manager.update_company_state(company_id, 'webhook_config', config)
                    return config.get(webhook_key)
                except json.JSONDecodeError:
                    return None
            elif isinstance(config, dict):
                return config.get(webhook_key)
                
        return None
        
    async def _forward_to_webhook(self, webhook_url, data):
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=data) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Webhook error: {response.status}, {response_text}")
                    else:
                        logger.info(f"Successfully forwarded outgoing message to webhook")
        except Exception as e:
            logger.error(f"Error forwarding to webhook: {str(e)}")