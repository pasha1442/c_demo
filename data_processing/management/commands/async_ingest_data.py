"""Process data enrichment requests in batches"""
from django.core.management.base import BaseCommand
from data_processing.models import DataIngestion
from data_processing.services.async_data_ingestion_service import AsyncDataIngestionService
from backend.logger import Logger
from datetime import datetime
# Configure logger
logger = Logger(Logger.INFO_LOG)
import sentry_sdk
from sentry_sdk import start_transaction
from backend.settings.base import SENTRY_DSN_URL

# Initialize Sentry
sentry_sdk.init(
    dsn=SENTRY_DSN_URL,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)


# python manage.py async_ingest_data
class Command(BaseCommand):
    help = 'Process data ingestion requests using asyncio'


    def handle(self, *args, **options):

        with start_transaction(op="DjangoCommand", name="Data Ingestion"): 
            self.runhandle()


    def runhandle(self, *args, **options):
        logger.add("Starting data enrichment batch processing")
        print("Starting data enrichment batch processing")

        # Get pending data enrichment requests
        pending_requests = DataIngestion.without_company_objects.filter(
            status__in=[DataIngestion.STATUS_PENDING]
        )
        request_count = pending_requests.count()
        logger.add(f"Found {request_count} pending requests to process")
        print(f"Found {request_count} pending requests to process")

        if not pending_requests.exists():
            self.stdout.write(self.style.WARNING('No pending requests found'))
            return

        for request in pending_requests:
            try:
                logger.add(f"Processing request ID: {request.id}")
                print(f"Processing request ID: {request.id}")
                async_ingestion_service = AsyncDataIngestionService()

                async_ingestion_service.ingest_data(request)
                logger.add("Initialized DataEnricher service")
                print("Initialized DataEnricher service")
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully processed request {request.id}')
                )
            except Exception as e:
                error_msg = f"Error processing request {request.id}: {str(e)}"
                print("Error:", str(error_msg))
                logger.add(error_msg)
                request.status = DataIngestion.STATUS_ERROR
                request.metadata = {
                    **(request.metadata or {}),
                    "error": {
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                request.save()
