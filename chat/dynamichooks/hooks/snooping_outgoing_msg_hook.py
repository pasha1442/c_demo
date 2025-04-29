from chat.dynamichooks.base_dynamic_hooks import BaseDynamicHooks
import aiohttp
import json
import logging

logger = logging.getLogger(__name__)

class SnoopingOutgoingMsgHook(BaseDynamicHooks):
   
    async def execute(self, company, state):
        
        logger.info(f"Processing outgoing message hook for {state.get('client_identifier')}")
        
        webhook_url = self._get_webhook_url(company)
        if not webhook_url:
            logger.warning(f"No webhook URL configured for company {company.id}")
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
    
    def _get_webhook_url(self, company):
        """Get the webhook URL from company attributes"""
        if hasattr(company, 'webhook_config') and company.webhook_config:
            config = json.loads(company.webhook_config) if isinstance(company.webhook_config, str) else company.webhook_config
            return config.get('snooping_outgoing_webhook_url')
        return None
        
    async def _forward_to_webhook(self, webhook_url, data):
        """Forward message data to webhook URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=data) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Webhook error: {response.status}, {response_text}")
                    else:
                        logger.info(f"Successfully forwarded message to webhook")
        except Exception as e:
            logger.error(f"Error forwarding to webhook: {str(e)}")
