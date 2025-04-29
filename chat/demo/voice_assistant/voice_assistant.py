import asyncio
import base64
import io
import time
import json
from asgiref.sync import sync_to_async
from chat import utils
from chat.clients.workflows.workflow_factory import WorkflowFactory
from chat.constants import CURRENT_ENVIRONMENT, GOOGLE_API_KEY
from chat.demo.voice_assistant.google_realtime_stt import GoogleSTT
from chat.demo.voice_assistant.google_realtime_tts import GoogleTTS
from chat.demo.voice_assistant.tools import *
from chat.assistants import get_active_prompt_from_langfuse
from chat.demo.voice_assistant.utils import calculate_audio_duration, calculate_cost, calculate_pcm16_duration, pcm_data_speech_to_text, openai_generation_langfuse
from chat.services.chat_history_manager.chat_message_saver import ChatMessageSaverService
import audioop
from pydub import AudioSegment

from langfuse.decorators import langfuse_context, observe
from chat.services.chat_history_manager.in_memory_chat_history_service import InMemoryChatHistoryService
from metering.services.openmeter import OpenMeter
from openai import OpenAI
import google.generativeai as genai
from backend.logger import Logger
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage


workflow_logger = Logger(Logger.WORKFLOW_LOG)

    
class VoiceAssistantRunner:
    
    def __init__(self, openai_ws, api_controller):
        self.openai_ws = openai_ws
        self.total_duration = 0
        self.stream_sid = None
        self.last_message_start_time = 0
        self.close_client_connection = False
        self.api_controller = api_controller
        self.company = api_controller.company
        self.user_message_audio_pcm = b""
        self.caller_phone_number = None
        self.ai_phone_number = None
        self.audio_type = 'g711_ulaw'
        self.session_id = None
        self.current_langfuse_trace_id = None
        self.language = 'english'
        
    
    @observe()
    async def initialize_config(self, data):
        try:
            self.current_langfuse_trace_id = langfuse_context.get_current_trace_id()
    
            self.stream_sid = data['start']['streamSid']
            self.caller_phone_number = data['start']['customParameters']['from']
            self.ai_phone_number = data['start']['customParameters']['to']
            self.language = data['start']['customParameters']['language']
            
            if 'audio_type' in data['start']['customParameters']:
                self.audio_type = data['start']['customParameters']['audio_type']
                
                openmeter_obj = OpenMeter(company=self.company, api_controller=self.api_controller, request_args={"session_id":self.caller_phone_number})
                data['start']['customParameters']['session_id'] = openmeter_obj.billing_session_id
        
            self.stream_sid = data['start']['streamSid']
            self.session_id = data['start']['customParameters']['session_id']
            prompt_info = await sync_to_async(get_active_prompt_from_langfuse)(self.company.id, 'va-survey')
            self.prompt = prompt_info['system_prompt']
            self.ai_voice = prompt_info['ai_voice']['active'].lower()
                
            await self.send_session_update(self.openai_ws)
            langfuse_context.update_current_trace(user_id=self.caller_phone_number, session_id=self.session_id, name="Voice Assisant", tags=[CURRENT_ENVIRONMENT])
            
            workflow_logger.add("Config initialized!")

        except Exception as e:
            print("Error:", e)
            workflow_logger.add(f"Error in initialize config: {e}")
    
    async def send_session_update(self, openai_ws):
        """Send session update to OpenAI WebSocket."""
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": self.audio_type,
                "output_audio_format": self.audio_type,
                "voice": self.ai_voice,
                "instructions": self.prompt,
                "modalities": ["text", "audio"],
                "temperature": 0.6,
                "tools":tools
            }
        }
        print('Sending session update:', json.dumps(session_update))
        workflow_logger.add(f'Sending session update: {json.dumps(session_update)}')
        await openai_ws.send(json.dumps(session_update))
        
    async def send_to_openai(self, text_data):
        elapsed_time = time.time() - self.last_message_start_time
        if elapsed_time < self.total_duration: return 
        elif self.close_client_connection: return "close"
        else: self.total_duration = 0
                        
        data = json.loads(text_data)
        try:   
            if data['event'] == 'media' and self.openai_ws.open:
                audio_data = base64.b64decode(data['media']['payload'])
                
                pcm_data = audio_data
                if self.audio_type == 'g711_ulaw':
                    pcm_data = audioop.ulaw2lin(audio_data, 2)
                
                self.user_message_audio_pcm += pcm_data
                
                audio_payload = data['media']['payload']
                if self.audio_type == 'pcm16':
                    
                    audio = AudioSegment.from_raw(io.BytesIO(audio_data), sample_width=2, frame_rate=8000, channels=1)
                    pcm_audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2).raw_data
                    audio_payload = base64.b64encode(pcm_audio).decode()
                                
                audio_append = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_payload
                }         
                    
                await self.openai_ws.send(json.dumps(audio_append))
            
            elif data['event'] == 'start':
                await self.initialize_config(data)
                print(f"Incoming stream has started {self.stream_sid}")
        
        except Exception as e:
            print(f"Error in send_to_openai: {e}")
            workflow_logger.add(f"Error during send_to_openai: {e}")
                
    async def send_to_client(self, client_socket):
        """Receive events from the OpenAI Realtime API, send audio back to client."""
        openai_response_start = False
        try:
            async for openai_message in self.openai_ws:
                response = json.loads(openai_message)
                    
                if response['type'] == 'response.audio.delta' and response.get('delta'):
                    
                    if not openai_response_start:                        
                        self.last_message_start_time = time.time()
                        openai_response_start = True
                    
                    audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                    
                    audio_delta = {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {
                            "payload": audio_payload
                        }
                    }
                    if self.audio_type == 'pcm16': self.total_duration += calculate_pcm16_duration(response['delta'], sample_rate=24000)
                    else: self.total_duration += calculate_audio_duration(response['delta'])
                    
                    await client_socket.send(text_data=json.dumps(audio_delta))
                
                if response['type'] == "response.done":
                    openai_response_start = False
                    await self.save_messages(response, langfuse_parent_trace_id=self.current_langfuse_trace_id)
                    workflow_logger.add(f"Openai response: {response}")
                    
        except Exception as e:
            print(f"Error in send_to_client: {e}")
            workflow_logger.add(f"Error in send_to_client: {e}")
            
    @observe(name="Openai Generation")
    async def save_messages(self, response, **kwargs):
        
        user_message = await pcm_data_speech_to_text(self.user_message_audio_pcm, self.language)
        self.user_message_audio_pcm = b""
        
        ai_message = ""
        function_arguments = ""
        function_name = None
        for message in response['response']['output']:
            if message['type'] == 'message':
                for audio_data in message['content']:
                    ai_message += audio_data['transcript']+"\n"
            elif message['type'] == 'function_call':
                function_arguments = message['arguments']
                function_name = message['name']
        
        
        token_usage = response['response']['usage']
        token_usage["prompt_tokens"] = response['response']['usage']["input_tokens"]
        token_usage["completion_tokens"] = response['response']['usage']["output_tokens"]
        token_usage['total_cost'] = calculate_cost(token_usage)
        input_messages = [{'role': 'system', 'content': self.prompt}, {'role': 'user', 'content':user_message}]
        openai_generation_langfuse("gpt-4o-realtime-preview", token_usage, input_messages, ai_message)
        
        
        extra_save_data = {
            "session_id": self.session_id,
            "client_identifier":self.caller_phone_number[3:]
        }
        await sync_to_async(utils.save_conversation)(self.company, 'user', self.caller_phone_number, user_message, extra = extra_save_data)
        await sync_to_async(utils.save_conversation)(self.company, 'assistant', self.caller_phone_number, ai_message, extra = extra_save_data)
        
        if function_name:
            arguments = json.loads(function_arguments)
            arguments['phone_number'] = self.caller_phone_number
            arguments['session_id'] = self.session_id
            func = globals()[function_name]
            result = await func(**arguments)
            
            self.close_client_connection = True
            await self.openai_ws.close()
            workflow_logger.add("Openai connection closed!")
            

class VoiceAssistantCustom:
    def __init__(self, api_controller, client_socket, language='in_english', api_route=None, openai_ws=None):
        self.input_audio_queue = asyncio.Queue()
        self.input_text_queue = asyncio.Queue()
        self.output_text_queue = asyncio.Queue()
        self.output_audio_queue = asyncio.Queue()
        self.running_openai_tasks = []
        self._active = True
        self.audio_type = 'g711_ulaw'
        self.client_socket = client_socket
        self.api_controller = api_controller
        self.company = api_controller.company
        self.openai_client = OpenAI()
        self.google_stt = GoogleSTT(language)
        self.openai_realtime_socket = openai_ws
        self.current_output_speech_duration = 0
        self.last_message_start_time = 0
        # self.close_client_connection = False
        self.prompt = "You are helpful assistant."
        self.api_route = api_route
        self.language = language
        self.chat_saver = ChatMessageSaverService(company=self.company, api_controller=self.api_controller)
        
        self.interruption_time = time.time()
        self.is_user_speaking = False
        self.sent_audio_duration = 0
        self.output_message = ''

        self.method = api_controller.voice_assistant_method if api_controller.voice_assistant_method else 'workflow'        
        self.interruption_enabled = api_controller.voice_assistant_interruption
        
        genai.configure(api_key=GOOGLE_API_KEY)
        self.gemini_model = genai.GenerativeModel("gemini-1.5-flash-8b")
    
    async def prompt_initialize(self):
        try:
            prompt_info = await sync_to_async(get_active_prompt_from_langfuse)(self.company.id, 'va-prompt')
            self.prompt = prompt_info['system_prompt']
        except Exception as e:
            print("Error:", e)
            workflow_logger.add(f"Company: {self.company} | Error in prompt initialize: {e}")
        
    async def initialize_config(self, data):
        try:
            self.current_langfuse_trace_id = langfuse_context.get_current_trace_id()
            
            self.google_tts = GoogleTTS(data['start']['customParameters']['ai_voice_gender'], self.language)
            self.client_socket.processing_tts_task = asyncio.create_task(self.process_output_text())
            
            self.call_sid = data['start']['callSid']
            self.stream_sid = data['start']['streamSid']
            self.caller_phone_number = data['start']['customParameters']['from']
            
            self.client_session_id = self.call_sid
            
            if 'audio_type' in data['start']['customParameters']:
                self.audio_type = data['start']['customParameters']['audio_type']
                
            await self.send_session_update()
            langfuse_context.update_current_trace(user_id=self.caller_phone_number, name="Voice Assisant", tags=[CURRENT_ENVIRONMENT])
            
            workflow_logger.add("Config initialized!")

        except Exception as e:
            print("Error:", e)
            workflow_logger.add(f"Company: {self.company} | Client session id: {self.client_session_id} | Error: {e}")
        
    async def send_session_update(self):
        """Send session update to OpenAI WebSocket."""
        
        session_update = {
            "type": "session.update",
            "session": {
                
                "instructions": self.prompt,
                "modalities": ["text"],
                "temperature": 0.6,
                "tools":tools
            }
        }

        # print('Sending session update:', json.dumps(session_update))
        # logger.info(f'Company: {self.company} | Session id: {self.session_id} | Sending session update: {json.dumps(session_update)}')
        # await self.openai_realtime_socket.send(json.dumps(session_update))
        
    async def cancel_all_running_openai_tasks(self):
        for task in self.running_openai_tasks:
            if self.openai_task != task:
                print("cancelling task")
                task.cancel()
                try:
                    await task  # Ensure task gets a chance to cancel
                except asyncio.CancelledError:
                    print("process send to openai task canceled")
                
        #calculating number of words sent, assuming 2.5 words per second
        self.output_audio_queue = asyncio.Queue()
        
        sent_output_text = ''
        if self.sent_audio_duration and self.sent_audio_duration > 1.5:
            
            number_of_words_sent = int(self.sent_audio_duration*2.5)
            sent_output_text = ' '.join(self.output_message.split(' ')[:number_of_words_sent])
            extra_save_data = {'session_id': self.session_id, 'client_session_id': self.client_session_id,  'client_identifier':self.caller_phone_number}
            await self.chat_saver.save_message(company=self.company, role='assistant', mobile_number=self.caller_phone_number, message=sent_output_text, extra_save_data=extra_save_data, client_identifier=self.caller_phone_number)
        
        if self.output_message:
            try:
                workflow_factory_obj = WorkflowFactory()
                workflow_name = self.company.name + "_" + self.api_controller.api_route
                workflow_type = self.api_controller.workflow_type
                workflow_json = self.api_controller.graph_json
                
                app = workflow_factory_obj.get_workflow(workflow_name, workflow_json, workflow_type=workflow_type)
                
                
                config = {"configurable": {"thread_id": self.session_id}}
                last_state = await app.aget_state(config)
                messages = last_state.values['messages']
                
                if len(messages) > 0:
                    
                    remove_messages = []
                    i = len(messages)-1
                    while i >= 0 and not isinstance(messages[i], HumanMessage): 
                        remove_messages.append(RemoveMessage(id=messages[i].id))
                        i-=1
                    
                    if remove_messages:
                        await app.aupdate_state(config, {"messages": remove_messages})
            
                    if  sent_output_text:
                        print("inserting new ai message")    
                        await app.aupdate_state(config,{"messages": [AIMessage(content=sent_output_text)]})
                    
            except Exception as e:
                print("Error:", e)
                workflow_logger.add(f"Company: {self.company} | Session id: {self.session_id} | Error in cancel_all_running_openai_tasks: {e}")
        
        
        self.output_message = ''
        self.sent_audio_duration = 0

    
    async def process_send_to_openai(self):
        last_message = None
        processed = False
        while True:
            try:
                message = await asyncio.wait_for(self.input_text_queue.get(), timeout=1)
                last_message = message
                if last_message['is_final']:
                    if not processed :
                        # await self.cancel_all_running_openai_tasks()
                        self.openai_task = asyncio.create_task(self.process_request(last_message['transcript']))
                        self.running_openai_tasks.append(self.openai_task)
                        # await self.process_request(last_message['transcript'])
                    else: self.is_user_speaking = False
                    last_message = None
                    processed = False
                        
                
            except asyncio.TimeoutError:
                if last_message and not processed:
                    processed = True
                    # await self.process_request(last_message['transcript'])
                    # await self.cancel_all_running_openai_tasks()
                    self.openai_task = asyncio.create_task(self.process_request(last_message['transcript']))
                    self.running_openai_tasks.append(self.openai_task)
                    last_message = None
                    
                continue
            except Exception as e:
                print(f"Error in process_send_to_openai: {e}")
                workflow_logger.add(f"Company: {self.company} | Client Session id: {self.client_session_id} | Error in process_send_to_openai: {e}")
                break
            
    async def is_stop_command(self, message):
        prompt = f'''
            You are an AI assistant detecting user intent. Classify the user's input as:
            1. 'Wait' if they want the AI to pause.
            2. 'Stop' if they want the AI to stop entirely.
            3. 'Unclear' if their intent is ambiguous.

            Input: {message}

            Output the result in one word as follows: "wait" or "stop" or "unclear"
        '''
        
        response = self.gemini_model.generate_content(prompt)
        
        return response.text
            
    async def process_request(self, user_message):
        self.is_user_speaking = False
        elapsed_time = time.time() - self.last_message_start_time
        if elapsed_time <= self.current_output_speech_duration:
            if len(user_message.split()) <= 2:
                is_stop = ''
                try:
                    is_stop = await self.is_stop_command(user_message)
                except Exception as e:
                    print("Error:", e)
                    workflow_logger.add(f"Company: {self.company} | Client Session id: {self.client_session_id} | Error in is_stop_command: {e}")
                    
                print("Interruption:", user_message.split(), "is_stop", is_stop)
                
                if 'unclear' in is_stop.lower(): return 
             
        await self.cancel_all_running_openai_tasks()
        self.output_text_queue = asyncio.Queue()
        self.interruption_time = time.time()
        await self.client_socket.send(json.dumps({"event": "clear", "streamSid": self.stream_sid}))
        
        self.last_message_start_time = time.time()
        self.current_output_speech_duration = 2
        
        output_message = await self.get_llm_response(user_message)
        
        print("\n\noutput message", output_message)
        workflow_logger.add(f"Company: {self.company} | Session id: {self.session_id} | output message: {output_message}")
        
        if self.method != 'workflow': await self.save_message(user_message, output_message)
        
    async def input_audio_generator(self):
        silent_frame = b'\x00\x00' * 8000
        while self._active:
            try:
                # Wait for the next message with a timeout
                message = await asyncio.wait_for(self.input_audio_queue.get(), timeout=0.2)
                data = json.loads(message)
        
                elapsed_time = time.time() - self.last_message_start_time
                if elapsed_time <= self.current_output_speech_duration and not self.interruption_enabled:
                    yield silent_frame
                    continue
                 
            
                if data['event'] == 'start':
                    await self.initialize_config(data)
                elif data['event'] == 'media':
                    audio_data = base64.b64decode(data['media']['payload'])
                    if self.audio_type == 'g711_ulaw':
                        audio_data = audioop.ulaw2lin(audio_data, 2)
                    yield audio_data
                         
            except asyncio.TimeoutError:
                yield silent_frame
                continue
            except Exception as e:
                print(f"Error in message generator: {e}")
                workflow_logger.add(f"Company: {self.company} | Client session id: {self.client_session_id} | Error: {e}")
                break 
        self._active = False
        
    @observe()    
    async def process_input_audio(self):
        try:
            stt_stream = await self.google_stt.process_audio(self.input_audio_generator())
            
            print("Speech to text initialized!")
            async for text_chunk in stt_stream:
                if text_chunk.results and text_chunk.results[0].alternatives[0].transcript:
                    self.is_user_speaking = True
                    
                    transcript = text_chunk.results[0].alternatives[0].transcript
                    chunk_data = {'transcript': transcript, 'is_final': False}
                    if text_chunk.results[0].is_final: chunk_data['is_final'] = True
                
                    await self.input_text_queue.put(chunk_data)
                
                        
        except Exception as e:
            await self.process_input_audio()
            print("Error in process input:", e)
            workflow_logger.add(f"Company: {self.company} | Client session id: {self.client_session_id} | Error: {e}")
            
    async def save_message(self, input, output):
    
        chat_saver = ChatMessageSaverService(company=self.company, api_controller=self.api_controller)
        extra_save_data = {'message_type' : "text",'session_id' : self.session_id}
        await chat_saver.save_message(company=self.company, role='user', mobile_number=self.caller_phone_number, message=input, extra_save_data=extra_save_data, client_identifier=self.caller_phone_number)
        await chat_saver.save_message(company=self.company, role='assistant', mobile_number=self.caller_phone_number, message=output, extra_save_data=extra_save_data, client_identifier=self.caller_phone_number)
        
        
            
    @observe()        
    async def get_llm_response(self, user_message):
        from api_controller.services.workflow_service import Workflow
        try:
            
            chat_history_service = InMemoryChatHistoryService(company=self.company, api_controller=self.api_controller, start_message=user_message, media_url="")
            session_data = chat_history_service.validate_conversation_session(company=self.company, client_identifier=self.caller_phone_number)
            self.session_id = session_data['session_id']
            
        except Exception as e:
            print("Error:", e)
            workflow_logger.add(f"Company: {self.company} | Session id: {self.session_id} | Error in get_llm_response: {e}")
            
            
        if self.method == 'workflow':
            args = {'session_id': self.session_id, 'mobile_number': self.caller_phone_number, 'client_identifier': self.caller_phone_number, 'message':{'text':user_message}, 'client_session_id':self.client_session_id, 'session_validated':True, 'save_ai_message': False}
            workflow = Workflow(company=self.company, api_controller=self.api_controller, request_args=args)
            llm_response_generator = workflow.init_workflow(route=self.api_route)
        else:
            llm_response_generator = self.get_openai_realtime_response(user_message)
        
        self.output_message = ''
        async for data in llm_response_generator:
            
            self.output_message += data
            await self.output_text_queue.put(data)
        
        return self.output_message 
            
    async def output_text_generator(self):
        while True:
            try:
                message = await asyncio.wait_for(self.output_text_queue.get(), timeout=3)
                yield message
                
            except asyncio.TimeoutError:
                yield ' '    
                continue
            except Exception as e:
                print(f"Error in output_text_generator: {e}")
                workflow_logger.add(f"Company: {self.company} | Session id: {self.session_id} | Error in output_text_generator: {e}")
                break
            
        print("output text generator finished")
            
    async def process_output_text(self):
        tts_stream = self.google_tts.process_text(self.output_text_generator())
        print("Text to Speech Initialized.")
        async for audio_data in tts_stream:
            if time.time()-self.interruption_time <= 1:
                continue
            
            encoded_audio_data = base64.b64encode(audio_data).decode('utf-8')
            self.current_output_speech_duration += calculate_pcm16_duration(encoded_audio_data, sample_rate=24000)
            
            if self.audio_type == 'g711_ulaw':
                audio = AudioSegment.from_raw(io.BytesIO(audio_data), sample_width=2, frame_rate=24000, channels=1)
                audio_data = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2).raw_data
                audio_data = audioop.lin2ulaw(audio_data, 2)
                encoded_audio_data = base64.b64encode(audio_data).decode('utf-8')
            
            audio_delta = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload":  encoded_audio_data
                }
            }
    
            # await self.client_socket.send(json.dumps(audio_delta))
            # await asyncio.sleep(0)
            await self.output_audio_queue.put(audio_delta)
            
        print("Text to speech stopped.") 
        await self.process_output_text() 
        
    async def send_output_audio_to_client(self):
        self.sent_audio_duration = 0
        
        while True:
            try:
                while self.is_user_speaking:
                    await asyncio.sleep(0.1)
                
                message = await asyncio.wait_for(self.output_audio_queue.get(), timeout=0.5)
                await self.client_socket.send(json.dumps(message))
                
                chunk_duration = 0
                if self.audio_type == 'g711_ulaw': chunk_duration = calculate_audio_duration(message['media']['payload'])
                else: chunk_duration = calculate_pcm16_duration(message['media']['payload'], sample_rate=24000)
                
                await asyncio.sleep(max(0,chunk_duration-0.1))
                self.sent_audio_duration += chunk_duration
                
            except asyncio.TimeoutError:
                #saving ai message at the end speech, in case of no interruption
                if self.sent_audio_duration > 1 and self.output_message:
                    self.sent_audio_duration = 0
                    extra_save_data = {'session_id': self.session_id, 'client_session_id': self.client_session_id, 'client_identifier':self.caller_phone_number}
                    await self.chat_saver.save_message(company=self.company, role='assistant', mobile_number=self.caller_phone_number, message=self.output_message, extra_save_data=extra_save_data, client_identifier=self.caller_phone_number)
                    self.output_message = ''
                
            except Exception as e:
                print(f"Error in send_output_audio_to_client: {e}")
                workflow_logger.add(f"Company: {self.company} | Client Session id: {self.client_session_id} | Error in send_output_audio_to_client: {e}")
                break
            
    async def get_openai_realtime_response(self, user_message):
        event1 = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_message
                    }
                ]
            }
        }
        
        event2 = {
            "type": "response.create",
            "response": {
                "modalities": ["text"],
                "instructions": self.prompt
            }
        }
        
        await self.openai_realtime_socket.send(json.dumps(event1))
        await self.openai_realtime_socket.send(json.dumps(event2))
        function_name = None
        function_arguments = ''
        async for openai_message in self.openai_realtime_socket:
            response = json.loads(openai_message)
            if response['type'] == 'response.text.delta' and response.get('delta'):
                yield response.get('delta')
            
            if response['type'] == 'response.done':
                for message in response['response']['output']:
                    if message['type'] == 'function_call':
                        function_arguments = message['arguments']
                        function_name = message['name']
                        if function_name:
                            print("Tool call")
                            arguments = json.loads(function_arguments)
                            arguments['phone_number'] = self.caller_phone_number
                            arguments['session_id'] = self.session_id
                            func = globals()[function_name]
                            await func(**arguments)
                            
                            # self.close_client_connection = True
                            workflow_logger.add("Openai connection closed!")
                            
                            await self.openai_realtime_socket.close()
                            
                            
                            
                break
    
