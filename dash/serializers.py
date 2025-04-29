from django.contrib.auth import get_user_model
from rest_framework import serializers
from dash.models import ApiKey
from .models import Service

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'name_of_organisation', 'phone_number', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        # Generate API key here and save it to user.api_key, then return user
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ['id','key','created_at']
        read_only_fields = ('id', 'created_at')


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'name', 'cost']

# class UserServicesSerializer(serializers.ModelSerializer):
#     services = serializers.SerializerMethodField()

#     class Meta:
#         model = Client
#         fields = ['services']
    
#     def get_services(self, obj):
#         request = self.context.get('request')
#         services = obj.services.all()
#         return [
#             {
#                 **ServiceSerializer(service).data,
#                 "subscribed": True
#             }
#             for service in services
#         ]
