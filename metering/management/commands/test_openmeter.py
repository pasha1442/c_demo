from django.core.management.base import BaseCommand
from metering.services.openmeter import OpenMeter

from django.apps import apps


class Command(BaseCommand):
    help = "*"

    def handle(self, *args, **options):
        try:
            OpenMeter()
            self.stdout.write(self.style.SUCCESS("Successful"))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(str(ex)))
