from django.core.management.base import BaseCommand
from services.service import ServiceProcessor


class Command(BaseCommand):
    help = "archive Database"

    def handle(self, *args, **options):
        try:
            ServiceProcessor().process_scheduled_apis()
            self.stdout.write(self.style.SUCCESS("Success"))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(str(ex)))

