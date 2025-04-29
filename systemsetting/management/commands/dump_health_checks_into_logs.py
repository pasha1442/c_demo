import json
from datetime import datetime
from django.core.management.base import BaseCommand
from systemsetting.services.system_health_check_service import HealthCheckService
from backend.logger import Logger

health_logger = Logger(Logger.HEALTH_LOG)

# */5 * * * * /path/to/your/virtualenv/bin/python /path/to/your/project/manage.py check_health --logfile /path/to/health_check.log  # Cron command

class Command(BaseCommand):
    help = "Perform health checks for various system components"

    def add_arguments(self, parser):
        parser.add_argument(
            "--exclude",
            nargs="*",
            help="Specify health checks to exclude (e.g., --exclude celery db)",
            default=[]
        )

    def handle(self, *args, **options):
        excluded_checks = options["exclude"]

        health_status = self.check_health(excluded_checks)
        health_logger.health_info({"responses": health_status})

        self.stdout.write(self.style.SUCCESS(f"Health check completed."))

    def check_health(self, excluded_checks=None):
        health_service_list = ['kafka', 'db', 'cache', 'redis', 'storage', 'migration', 'celery', 'url_health_checker', 'system_services_health_checker']
        excluded_checks = excluded_checks or []

        response = {}
        for check_name in health_service_list:
            if check_name not in excluded_checks:
                result = HealthCheckService().dump_health_check_in_log_file(system_name=check_name)
                response.update(result)

        return response
