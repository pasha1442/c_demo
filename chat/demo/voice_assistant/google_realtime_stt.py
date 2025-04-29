import time
from google.cloud import speech
from google.oauth2.service_account import Credentials

from chat.constants import GOOGLE_APPLICATION_CREDENTIALS, STT_LANGUAGE_CODES
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)

#Realtime google speech to text
class GoogleSTT:
    
    def __init__(self, language):
        self.speech_client = speech.SpeechAsyncClient(credentials=Credentials.from_service_account_file(GOOGLE_APPLICATION_CREDENTIALS))
        streaming_config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=8000,
                language_code=STT_LANGUAGE_CODES[language],
            ),
            interim_results=True,
        )
        self.config_request = speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        
        
    async def google_speech_generator(self, audio_generator):
        yield self.config_request
        async for audio_chunk in audio_generator:
            yield speech.StreamingRecognizeRequest(audio_content=audio_chunk)
        
    async def process_audio(self, audio_generator):
        try:
            stt_stream = await self.speech_client.streaming_recognize(requests=self.google_speech_generator(audio_generator))
            
            return stt_stream
        except Exception as e:
            print("Error in google tts:", e)
            workflow_logger.add(f"Error in google tts: {e}")
                