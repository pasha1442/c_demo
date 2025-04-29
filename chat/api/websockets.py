import asyncio
from api_controller.models import ApiController
from chat.constants import ENABLE_LANGFUSE_TRACING
from chat.demo.voice_assistant.voice_assistant import VoiceAssistantCustom, VoiceAssistantRunner
from channels.generic.websocket import AsyncWebsocketConsumer
from decouple import config
from langfuse.decorators import langfuse_context
from asgiref.sync import sync_to_async 
import websockets

from company.utils import CompanyUtils
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)

class MediaStreamConsumer(AsyncWebsocketConsumer):
    
    async def connect(self, agent_phone_number=''):            
        
        try:
            agent_phone_number = self.scope['url_route']['kwargs']['agent_phone_number']
            api_controller = await sync_to_async(CompanyUtils.get_api_controller_from_phone_number)(agent_phone_number)
            
            langfuse_context.configure(secret_key=api_controller.company.langfuse_secret_key,public_key=api_controller.company.langfuse_public_key,enabled = ENABLE_LANGFUSE_TRACING)
            
            openai_ws = await initialize_openai_realtime_websocket()    
            self.voice_assistant = VoiceAssistantRunner(openai_ws, api_controller)
            await self.accept()
            asyncio.create_task(self.voice_assistant.send_to_client(self))
        except Exception as e:
            print("Error: ", e)
            workflow_logger.add(f"Error: {e}")
        
        workflow_logger.add("Websocket client connected!")
            
    async def disconnect(self, close_code):
        print("Disconnected...")
        self.voice_assistant.openai_ws.close()
        workflow_logger.add("openai client disconnected!")
        workflow_logger.add("Websocket client disconnected!")
        
    async def receive(self, text_data):
        res = await self.voice_assistant.send_to_openai(text_data)
        if res:
            await self.close_connection()
        
        
    async def close_connection(self):
        if self.channel_layer:
            await self.channel_layer.group_discard(self.channel_name, self.channel_name)
    
        if hasattr(self, 'send_task'):
            self.send_task.cancel()
        
        if hasattr(self, 'voice_assistant') and self.voice_assistant.openai_ws and self.voice_assistant.openai_ws.open:
            await self.voice_assistant.openai_ws.close()
            
        await self.close(code=1000) 
        
        
        
class VoiceAssistantMediaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        
        try:
            language = self.scope['url_route']['kwargs']['language']
            agent_phone_number = self.scope['url_route']['kwargs']['agent_phone_number']
            api_route = self.scope['url_route']['kwargs']['api_route']
            
            #Retrieving voice api_controller which contains phone number in order to get the company because we cannot get company from phone number directly
            #We are doing this because one of voice assitant's api_controller is associated with phone number and not with company
            api_controller_with_phone = await sync_to_async(CompanyUtils.get_api_controller_from_phone_number)(agent_phone_number)
            company = api_controller_with_phone.company
            
            #This is the real api_controller corresponding to the api_route and company
            api_controller = await sync_to_async(ApiController.without_company_objects.get)(api_route=api_route, company=company)
            api_controller.company = company
            
            langfuse_context.configure(secret_key=api_controller.company.langfuse_secret_key,public_key=api_controller.company.langfuse_public_key,enabled = ENABLE_LANGFUSE_TRACING)
            
            # self.openai_ws = await initialize_openai_realtime_websocket()
            self.voice_assistant = VoiceAssistantCustom(api_controller, self, language, api_route=api_route)
            await self.voice_assistant.prompt_initialize()
            
            
            self.processing_stt_task = asyncio.create_task(self.voice_assistant.process_input_audio())
            self.process_sent_to_openai_task = asyncio.create_task(self.voice_assistant.process_send_to_openai())
            self.process_send_output_audio_to_client_task = asyncio.create_task(self.voice_assistant.send_output_audio_to_client())
            
            await self.accept()
            
        except Exception as e:
            workflow_logger.add(f"Error: {e}")

        
        workflow_logger.add("Websocket client connected!")
        print("Websocket client connected!")
        
            
    async def disconnect(self, close_code):
        print("Disconnected...")
        try:
            if self.processing_stt_task.cancel():
                print("process stt task canceled")
            if self.process_sent_to_openai_task.cancel():
                print("process send to openai task canceled")
            if self.processing_tts_task.cancel():
                print("process TTS task canceled")
            if hasattr(self,'openai_ws') and self.openai_ws.open:
                await self.openai_ws.close()
            if self.process_send_output_audio_to_client_task.cancel():
                print("process send output audio to client task canceled")
        except Exception as e:
            print("Error:", e)
        workflow_logger.add("Websocket client disconnected!")
        
    async def receive(self, text_data):
        try:
            await self.voice_assistant.input_audio_queue.put(text_data)
    
            if not self.voice_assistant._active: 
                await self.close_connection()
        except Exception as e:
            print("Error in receive:", e)
        
        
    async def close_connection(self):
        print("closing connection")
        if self.channel_layer:
            await self.channel_layer.group_discard(self.channel_name, self.channel_name)
        
        if self.processing_stt_task.cancel():
            print("process stt task canceled")
        if self.process_sent_to_openai_task.cancel():
            print("process send to openai task canceled")
        if self.processing_tts_task.cancel():
            print("process TTS task canceled")
        if hasattr(self,'openai_ws') and self.openai_ws.open:
            await self.openai_ws.close()
        if self.process_send_output_audio_to_client_task.cancel():
            print("process send output audio to client task canceled")
        await self.close(code=1000) 
        
        
async def initialize_openai_realtime_websocket():
    OPENAI_API_KEY = config('OPENAI_API_KEY')
    openai_ws = await websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    )
    print("Openai realtime api initialized:", openai_ws.open)
    return openai_ws