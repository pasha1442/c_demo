import uuid
from rest_framework_simplejwt.tokens import RefreshToken

def generate_api_key():
    return 'kl-' + str(uuid.uuid4())

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)