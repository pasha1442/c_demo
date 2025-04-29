from django.core.management.base import BaseCommand
from data_processinga.services.kafka_service import BaseKafkaService
from django.apps import apps


class Command(BaseCommand):
    help = "List Topics"

    def handle(self, *args, **options):
        try:
            _queue_list = BaseKafkaService().get_queue_list()
            for _queue in _queue_list:
                print("-", _queue)
            self.stdout.write(self.style.SUCCESS("Executed"))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(str(ex)))
