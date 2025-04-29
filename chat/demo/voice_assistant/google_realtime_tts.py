import time
from google.cloud import texttospeech
from google.oauth2.service_account import Credentials
from chat.constants import AI_VOICE_CODES, GOOGLE_APPLICATION_CREDENTIALS, TTS_LANGUAGE_CODES
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)


#Realtime google text to speech
class GoogleTTS:
    def __init__(self, ai_voice_gender, language):
        self.tts_client = texttospeech.TextToSpeechAsyncClient(credentials=Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS))
        streaming_config = texttospeech.StreamingSynthesizeConfig(voice=texttospeech.VoiceSelectionParams(name=AI_VOICE_CODES[ai_voice_gender][language], language_code=TTS_LANGUAGE_CODES[language]))
        self.config_request = texttospeech.StreamingSynthesizeRequest(streaming_config=streaming_config)
        
        
    async def google_text_generator(self, text_generator):
        yield self.config_request
        async for chunk in text_generator:
            streaming_input = texttospeech.StreamingSynthesisInput(text=chunk)
            yield texttospeech.StreamingSynthesizeRequest(input=streaming_input)
        
    async def process_text(self, text_generator):
        start = time.time()
        first = False
        try:
            streaming_responses = await self.tts_client.streaming_synthesize(requests=self.google_text_generator(text_generator))
            async for response in streaming_responses:
                if not first:
                    first = True
                    print("text to speech first chunk", time.time()-start)
                yield response.audio_content
        except Exception as e:
            print("Error in google tts:", e)
            workflow_logger.add(f"Error in google tts: {e}")
                
                