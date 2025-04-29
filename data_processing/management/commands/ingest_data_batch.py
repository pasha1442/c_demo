from django.core.management.base import BaseCommand
from data_processing.models import DataIngestion
from backend.logger import Logger
from datetime import datetime
from data_processing.services.data_ingestion_service import DataIngestionService
import traceback
from data_processing.services.embedding_service import main

# Configure logger
logger = Logger(Logger.INFO_LOG)

# python manage.py ingest_data_batch
class Command(BaseCommand):
    help = 'Process one chunk from data ingestion requests'
    
    def add_arguments(self, parser):
        parser.add_argument('--id', type=str, default=None, 
                            help='Process a specific request by ID')
        # parser.add_argument('--retry-failed', action='store_true',
        #                     help='Retry a failed partition instead of processing pending ones')
    
    def handle(self, *args, **options):
        logger.add("Starting data ingestion single chunk processing")
        self.stdout.write(self.style.SUCCESS("Starting data ingestion single chunk processing"))
        
        specific_id = options.get('id')
        # retry_failed = options.get('retry_failed')
        
        # Get pending data ingestion requests
        query = DataIngestion.without_company_objects
        
        if specific_id:
            query = query.filter(id=specific_id)
        else:
            # Exclude completed jobs
            query = query.exclude(status=DataIngestion.STATUS_DONE)
        
        print(f"\n query : {query} \n")

        # Process the oldest request first
        pending_requests = query.order_by('created_at')[:1]
        print(f"\n pending_requests : {pending_requests} \n")
        # return
        # print("\n  \n")
        if not pending_requests.exists():
            self.stdout.write(self.style.WARNING('No pending requests found'))
            return
        
        request = pending_requests.first()
        ingestion_service = DataIngestionService(request)
        try:
            logger.add(f"Processing one chunk from request ID: {request.id}")
            self.stdout.write(f"Processing one chunk from request ID: {request.id}")
            
            # Show partition stats before processing
            # total_partitions = request.partitions.count()
            # done_partitions = request.partitions.filter(status='done').count()
            # error_partitions = request.partitions.filter(status='error').count()
            # pending_partitions = request.partitions.filter(status='pending').count()
            
            # self.stdout.write(f"Partitions: {done_partitions} done, {error_partitions} error, {pending_partitions} pending, {total_partitions} total")
            
            # Retry a failed partition if requested
            # if retry_failed and error_partitions > 0:
            #     retried = ingestion_service.retry_failed_partitions(request, limit=1)
            #     self.stdout.write(f"Retried {retried.get('retried', 0)} failed partition")
            
            # Process exactly one chunk
            chunk_processed = ingestion_service.process_ingestion_job(request)
            
            # Check completion status after processing
            ingestion_service.check_job_completion(request)
            
            # Get updated partition stats
            # total_partitions = request.partitions.count()
            # done_partitions = request.partitions.filter(status='done').count()
            # error_partitions = request.partitions.filter(status='error').count()
            # pending_partitions = request.partitions.filter(status='pending').count()
            
            if request.status == DataIngestion.STATUS_DONE:
                request.status = DataIngestion.DataIngested
                request.is_valid_embedding = True
                print(request.is_valid_embedding)
                request.save()
                
            if request.is_valid_embedding == True:
                main()
                request.embedding_generated_at = datetime.now()
                request.generate_embedding = True
                request.save()
                
            self.stdout.write(self.style.SUCCESS(
                f'Processed request {request.id} and embedding is genrated'
            ))
            
        except Exception as e:
            error_msg = f"Error processing request {request.id}: {str(e)}"
            logger.add(error_msg)
            self.stdout.write(self.style.ERROR(error_msg))
            
            # Log detailed error with traceback
            stack_trace = traceback.format_exc()
            logger.add(f"Traceback: {stack_trace}")
            
            # Update request status if a fatal error occurred
            request.status = DataIngestion.STATUS_ERROR
            request.save()