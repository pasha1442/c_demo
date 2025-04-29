from rest_framework import serializers
from django.db import models
from django.apps import apps
from chat.models import Conversations


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversations
        fields = ['id', 'company_id', 'role', 'mobile', 'message', 'message_id', 'function_name', 'created_at',
                  'message_metadata']
