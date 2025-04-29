from django.contrib.auth import get_user_model
from django.http import JsonResponse
from basics.middlewares import BaseMiddleware
from basics.utils import Registry
from rest_framework_simplejwt.tokens import AccessToken
from backend.constants import CURRENT_USER_ID

User = get_user_model()


class PostAuthenticationMiddleware(BaseMiddleware):

    def __init__(self, get_response=None):
        super().__init__(get_response)

    def process_request(self, request):
        header_token = request.META.get('HTTP_AUTHORIZATION', None)
        if request.user:
            reg = Registry()
            reg.set(CURRENT_USER_ID, request.user.id)
        elif header_token is not None:
            try:
                access_token_obj = AccessToken(header_token.split(' ')[1])
                user_id = access_token_obj['user_id']
                reg = Registry()
                reg.set(CURRENT_USER_ID, user_id)
            except:
                pass


class JWTAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_args = request.META.get('HTTP_AUTHORIZATION', ' ').split(' ')
        token = auth_args[1]
        if auth_args[0] == "Bearer":
            pass
        elif token:
            try:
                decoded_token = AccessToken(token)
                user_id = decoded_token.payload.get("user_id")
                user = User.objects.get(id=user_id)
                jwt_verification_code = decoded_token.payload.get("jwt_verification_code")
                if jwt_verification_code != user.jwt_verification_code:
                    return JsonResponse(
                        {"status": "INVALID_TOKEN", "message": "Token is invalid or expired"}, status=401)
            except Exception as ex:
                return JsonResponse(
                    {"error_code": 'INVALID_TOKEN', "message": str(ex)}, status=401
                )
        # else:
        #     if request.user.is_anonymous:
        #         return JsonResponse({"status": "INVALID_TOKEN", "message": "Token not found!"}, status=401)

        response = self.get_response(request)
        return response
