from django.core.management.base import BaseCommand
from data_processinga.services.kafka_service import BaseKafkaService
from django.apps import apps


class Command(BaseCommand):
    help = "Count all Topics Messages"

    def handle(self, *args, **options):
        try:
            _queue_list = BaseKafkaService().get_queue_list()
            for _queue in _queue_list:
                try:
                    print("queue", _queue, type(_queue))
                    print("-", _queue, BaseKafkaService(topic_name=_queue).get_queue_count())
                except Exception as e:
                    print("Exception:", str(e))
            self.stdout.write(self.style.SUCCESS("Executed"))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(str(ex)))
