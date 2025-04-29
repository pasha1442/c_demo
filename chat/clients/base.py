# base.py


class BaseOrganization:
    def process_request(self, request, text, mobile):
        raise NotImplementedError("This method should be implemented by subclasses.")