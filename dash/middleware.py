from django.http import JsonResponse
from dash.models import ClientSession

# class ValidateTokenMiddleware:
    # def __init__(self, get_response):
    #     self.get_response = get_response

    # def __call__(self, request):
    #     # Code to be executed for each request before
    #     # the view (and later middleware) are called.

    #     response = self.get_response(request)

    #     # Code to be executed for each request/response after
    #     # the view is called.

    #     return response

    # def process_view(self, request, view_func, view_args, view_kwargs):
    #     if 'HTTP_AUTHORIZATION' in request.META:
    #         token = request.META.get('HTTP_AUTHORIZATION').split(' ')[1]
    #         if not ClientSession.objects.filter(token=token).exists():
    #             return JsonResponse({'error': 'Invalid token'}, status=401)
    #     else:
    #         
    #         pass
