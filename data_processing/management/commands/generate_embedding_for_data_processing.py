from django.core.management.base import BaseCommand
from data_processing.models import DataEmbedding
from data_processing.services.embedding_service import main as embedding_service_main
from backend.logger import Logger
from datetime import datetime
import traceback

logger = Logger(Logger.INFO_LOG)

class Command(BaseCommand):
    help = 'Process data embeddings for Neo4j nodes'
    
    def add_arguments(self, parser):
        parser.add_argument('--id', type=str, default=None, 
                            help='Process a specific embedding job by ID')
        parser.add_argument('--label', type=str, default=None, 
                            help='Process a specific node label (if job ID provided)')
    
    def handle(self, *args, **options):
        logger.add("Starting data embedding processing")
        self.stdout.write(self.style.SUCCESS("Starting data embedding processing"))
        
        specific_id = options.get('id')
        specific_label = options.get('label')
        
        try:
            if specific_id:
                self.stdout.write(f"Processing embedding job ID: {specific_id}")
                logger.add(f"Processing embedding job ID: {specific_id}")
                
                job = DataEmbedding.without_company_objects.get(id=specific_id)
                
                if specific_label:
                    self.stdout.write(f"Focusing on specific label: {specific_label}")
                    job.node_labels = [specific_label]
                    job.save()
                
                success = embedding_service_main(specific_id)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully processed embedding job {specific_id}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to process embedding job {specific_id}')
                    )
                
            else:
                pending_jobs = DataEmbedding.without_company_objects.filter(
                    status=DataEmbedding.STATUS_PENDING
                ).order_by('created_at')
                
                if not pending_jobs.exists():
                    self.stdout.write(self.style.WARNING('No pending embedding jobs found'))
                    return
                
                job = pending_jobs.first()
                self.stdout.write(f"Processing next pending job ID: {job.id}")
                logger.add(f"Processing next pending job ID: {job.id}")
                
                # Process the job
                success = embedding_service_main(job.id)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully processed embedding job {job.id}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to process embedding job {job.id}')
                    )
                
        except Exception as e:
            error_msg = f"Error processing embedding job: {str(e)}"
            logger.add(error_msg)
            self.stdout.write(self.style.ERROR(error_msg))
            
            stack_trace = traceback.format_exc()
            logger.add(f"Traceback: {stack_trace}")
            
            if specific_id:
                try:
                    job = DataEmbedding.without_company_objects.get(id=specific_id)
                    job.status = DataEmbedding.STATUS_ERROR
                    job.processing_error = error_msg
                    job.save()
                    self.stdout.write(self.style.WARNING(f"Updated job {specific_id} status to ERROR"))
                except Exception as update_error:
                    self.stdout.write(self.style.ERROR(f"Failed to update job status: {str(update_error)}"))