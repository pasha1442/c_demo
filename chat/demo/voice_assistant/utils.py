import base64
import json
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from google.oauth2.service_account import Credentials
from google.cloud import speech
from decouple import config
from langfuse.decorators import langfuse_context, observe
from backend.logger import Logger
from twilio.rest import Client
from chat.constants import CORE_BACKEND_BASE_URL, GOOGLE_APPLICATION_CREDENTIALS, STT_LANGUAGE_CODES


workflow_logger = Logger(Logger.WORKFLOW_LOG)

def start_twilio_stream(request, session_id):
    caller = request.POST.get("From")
    agent = request.POST.get("To")

    response = VoiceResponse()
    response.say("Please wait while we connect you to assistant")
    response.pause(1)
    response.say("Ok you can start talking")
    
    host = request.get_host()
    ws_url = f'wss://{host}/media-stream/{agent[1:]}'
    
    connect = Connect()
    stream = Stream(url=ws_url)
    stream.parameter(name="from", value=caller) 
    stream.parameter(name="to", value=agent) 
    stream.parameter(name="session_id", value=session_id) 
    
    connect.append(stream)
    response.append(connect)
    
    return response

def initiate_call(company_id, customer_phone_number, session_id, metadata):
    
    try:
        language = metadata['language'] if metadata['language'] else 'in_english'
        ai_voice_gender = metadata['ai_voice_gender'] if metadata['ai_voice_gender'] else 'male'
        workflow = metadata['workflow'] if metadata['workflow'] else 'default'
        agent_phone_number = metadata['agent_phone_number']
        
        account_sid = config("TWILIO_ACCOUNT_SID")
        auth_token = config('TWILIO_AUTH_TOKEN')
        twiml_base_url = config('TWILIO_TWIML_BIN_URL')
        twiml_url = (
            f"{twiml_base_url}?"
            f"from={customer_phone_number.split('-')[1]}&to={agent_phone_number}&session_id={session_id}&language={language}&ai_voice_gender={ai_voice_gender}&workflow={workflow}"
        )
        client = Client(account_sid, auth_token)
        
        call = client.calls.create(
            to=customer_phone_number,
            from_=agent_phone_number,
            url=twiml_url ,
            status_callback=f"{CORE_BACKEND_BASE_URL}/api/v1/chat/voice-assistant/voice-call-status-callback?company_id={company_id}&workflow={workflow}",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed']
        )
        print(f"Call initiated successfully. SID: {call.sid}")
        response = {'call_sid': call.sid, 'session_id': session_id, 'status_code':200}
           
        return json.dumps(response)
    except Exception as e:
        print(f"Error occurred: {e}")
        response = {'error': f'Error occured: {e}', 'status_code':500}
        return json.dumps(response)

async def pcm_data_speech_to_text(audio_data, language):
    try:
        gcp_creds = Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS)
        client = speech.SpeechClient(credentials=gcp_creds)
        gcp_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, 
            sample_rate_hertz=8000, 
            language_code=STT_LANGUAGE_CODES[language]
        )
        
        audio = speech.RecognitionAudio(content=audio_data)
        response = client.recognize(config=gcp_config, audio=audio)
        if response.results:
            text = response.results[0].alternatives[0].transcript
            return text
        else:
            workflow_logger.add("Speech was unrecognizable!")
            return "Speech was unrecognizable!"
    except Exception as e:
        workflow_logger.add(f"Error with Google Cloud Speech-to-Text: {e}")
        print(f"Error with Google Cloud Speech-to-Text: {e}")
        return "Error in translating speech to text."
    
def calculate_audio_duration(audio, sample_rate=8000):
    audio_data = base64.b64decode(audio)
    num_samples = len(audio_data)
    duration = num_samples / sample_rate
    return duration

@observe()
def openai_generation_langfuse(model, usage, input_messages, assistant_response):
    
    langfuse_client = langfuse_context.client_instance
    
    langfuse_client.generation(
        trace_id=langfuse_context.get_current_trace_id(),
        parent_observation_id=langfuse_context.get_current_observation_id(),
        model=model,
        usage=usage,
        input=input_messages,
        output=assistant_response
    )
    
    
def calculate_cost(token_details):
    """
    Calculate the cost of tokens based on the specified pricing scheme.
    
    :param token_details: Dictionary containing token information
    :return: Dictionary with detailed cost breakdown
    """
    # Text token pricing
    TEXT_INPUT_PRICE = 5.00 / 1_000_000  # $5 per million input tokens
    TEXT_CACHED_INPUT_PRICE = 2.50 / 1_000_000  # $2.50 per million cached input tokens
    TEXT_OUTPUT_PRICE = 20.00 / 1_000_000  # $20 per million output tokens
    
    # Audio token pricing
    AUDIO_INPUT_PRICE = 100.00 / 1_000_000  # $100 per million input tokens
    AUDIO_CACHED_INPUT_PRICE = 20.00 / 1_000_000  # $20 per million cached input tokens
    AUDIO_OUTPUT_PRICE = 200.00 / 1_000_000  # $200 per million output tokens
    
    # Extract token details
    text_input_tokens = token_details['input_token_details']['text_tokens']
    audio_input_tokens = token_details['input_token_details']['audio_tokens']
    cached_text_tokens = token_details['input_token_details']['cached_tokens_details']['text_tokens']
    cached_audio_tokens = token_details['input_token_details']['cached_tokens_details']['audio_tokens']
    
    text_output_tokens = token_details['output_token_details']['text_tokens']
    audio_output_tokens = token_details['output_token_details']['audio_tokens']
    
    # Calculate costs
    text_input_cost = text_input_tokens * TEXT_INPUT_PRICE
    audio_input_cost = audio_input_tokens * AUDIO_INPUT_PRICE
    
    cached_text_input_cost = cached_text_tokens * TEXT_CACHED_INPUT_PRICE
    cached_audio_input_cost = cached_audio_tokens * AUDIO_CACHED_INPUT_PRICE
    
    text_output_cost = text_output_tokens * TEXT_OUTPUT_PRICE
    audio_output_cost = audio_output_tokens * AUDIO_OUTPUT_PRICE
    
    # Total cost calculation
    total_cost = (
        text_input_cost + 
        audio_input_cost + 
        cached_text_input_cost + 
        cached_audio_input_cost + 
        text_output_cost + 
        audio_output_cost
    )

    return total_cost


def calculate_pcm16_duration(audio_data, sample_rate, channels=1):
    
    total_bytes = len(base64.b64decode(audio_data))
    bytes_per_sample = 2  
    duration = total_bytes / (sample_rate * channels * bytes_per_sample)
    return duration