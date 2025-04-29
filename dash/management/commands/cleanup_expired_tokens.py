from django.core.management.base import BaseCommand
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.tokens import UntypedToken, TokenError

class Command(BaseCommand):
    help = 'Delete expired tokens from the ClientSession table'

    def handle(self, *args, **kwargs):
        for token in OutstandingToken.objects.all():
            try:
                # This will raise an error if the token is expired
                UntypedToken(token.token)
            except TokenError as e:
                # Token is expired, delete it
                BlacklistedToken.objects.get(token=token).delete()
                token.delete()
                self.stdout.write(self.style.SUCCESS('Deleted expired token for user %s' % token.user))
