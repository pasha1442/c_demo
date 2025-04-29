from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer
from django.contrib.auth import authenticate
from dash.models import ClientSession
from dash.models import ApiKey
from .serializers import ApiKeySerializer
from rest_framework.permissions import IsAuthenticated
from .utils import generate_api_key
from .models import Service
from .serializers import ServiceSerializer
from .utils import get_tokens_for_user
from django.db import connection
from django.contrib.auth import authenticate
# from company.admin import company_admin_site

User = get_user_model()

class UserRegistrationAPIView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Placeholder for API key generation logic
            # partition should be done at company registration
            # with connection.cursor() as cursor:
            #     cursor.execute(
            #         f"""
            #         CREATE TABLE IF NOT EXISTS conversations_company_{user.id} PARTITION OF conversations
            #         FOR VALUES IN ({user.id}); 
            #         """
            #     )
            
            return Response({
                'email': user.email, # type: ignore
                'name_of_organisation': user.name_of_organisation, # type: ignore
                'phone_number': user.phone_number, # type: ignore
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginAPIView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user:
            company_admin_site.set_company(user.company) # type: ignore
            token = get_tokens_for_user(user)
            ClientSession.objects.create(token=token)
            return Response({"token": token}, status=status.HTTP_200_OK)
        return Response({"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
    
class ApiKeyOperations(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        if request.method == 'GET':
            api_keys = ApiKey.objects.filter()
            serializer = ApiKeySerializer(api_keys, many=True)
            return Response(serializer.data)

    def post(self, request, format=None):
        if request.method == 'POST':
            api_key_value = generate_api_key()
            modified_request_data = request.data.copy()
            modified_request_data['key'] = api_key_value
            serializer = ApiKeySerializer(data=modified_request_data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, key_id, format=None):
        try:
            api_key = ApiKey.objects.get(id=key_id)
            api_key.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ApiKey.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

class ListServicesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        services = Service.objects.all()
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)
    
class UserServicesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user

        all_services = Service.objects.all()  # Get all services
        subscribed_services = set(user.services.all())  # User's subscriptions as a set
        
        serialized_data = []

        for service in all_services:
            serialized_service = ServiceSerializer(service).data
            serialized_service['subscribed'] = service in subscribed_services  # type: ignore # Check if subscribed
            serialized_data.append(serialized_service)

        return Response(serialized_data)

class UpdateClientServicesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        user = request.user
        services_to_add = request.data.get('service_ids', [])
        services_to_remove = request.data.get('services_to_remove', [])

        # Filter services to ensure they exist before adding
        if services_to_add:
            services = Service.objects.filter(id__in=services_to_add)
            if services.count() != len(services_to_add):
                return Response({'error': 'One or more services to add not found'}, status=status.HTTP_404_NOT_FOUND)
            user.services.add(*services)

        # Remove specified services
        if services_to_remove:
            services = Service.objects.filter(id__in=services_to_remove)
            if services.count() != len(services_to_remove):
                return Response({'error': 'One or more services to remove not found'}, status=status.HTTP_404_NOT_FOUND)
            user.services.remove(*services)

        user.save()
        return Response({'message': 'Services updated successfully'}, status=status.HTTP_200_OK)