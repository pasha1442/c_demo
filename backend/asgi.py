"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django_application = get_asgi_application()

from chat.api.websockets import MediaStreamConsumer, VoiceAssistantMediaConsumer

application = ProtocolTypeRouter({
    "http": django_application,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("media-stream/<str:agent_phone_number>", MediaStreamConsumer.as_asgi()), #This is for openai realtime api audio to audio
            path("voice-assistant/<str:agent_phone_number>/<str:language>/<str:api_route>", VoiceAssistantMediaConsumer.as_asgi()), #This is for STT-LLM-TTS pipeline(STT : speech to text, TTS : text to speech)
        ])
    ),
})