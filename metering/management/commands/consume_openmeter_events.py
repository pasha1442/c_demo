from django.core.management.base import BaseCommand
from metering.services.kafka.metering_kafka_consumer_service import MeteringKafkaConsumer
from backend.logger import Logger, LoggerWriter
import logging
import sys
from datetime import datetime


# python manage.py consume_openmeter_events

class Command(BaseCommand):
    help = "Consume Openmeter Events"

    def handle(self, *args, **options):
        # Get the logger
        logger = logging.getLogger('openmeter_info')
        # Add a console handler if not already added
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            logger.addHandler(console_handler)

        # Redirect print statements to the logger
        sys.stdout = LoggerWriter(logger.info)
        sys.stderr = LoggerWriter(logger.error)

        try:
            print(f"Open meter Consumer Started at: {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}")
            MeteringKafkaConsumer().consume_events_from_queue()
            self.stdout.write(self.style.SUCCESS("Executed"))
        except Exception as ex:
            logger.error(f"An error occurred: {ex}")
            self.stdout.write(self.style.ERROR(str(ex)))
