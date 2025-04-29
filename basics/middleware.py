from basics.admin import BaseAdminSite

class BaseMiddleware:

    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):

        BaseAdminSite().set_extra_context('user', request.user)
        response = None
        if hasattr(self, 'process_request'):
            response = self.process_request(request) # type: ignore

        response = response or self.get_response(request) # type: ignore

        if hasattr(self, 'process_response'):
            response = self.process_response(request, response) # type: ignore

        return response