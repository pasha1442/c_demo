from email.policy import default
from hashlib import blake2b

from requests import session
from django.db import models
import json
from django.db import models
from django.conf import settings
import time
from django.utils.translation import gettext_lazy as _
from pydantic import ValidationError
from basics.models import BaseModelCompleteUserTimestamps
from company.models import CompanyBaseModel
from django.utils import timezone
from basics.utils import UUID

def upload_as_input_file(instance, filename):
    # Files will be uploaded to MEDIA_ROOT/data_files/YYYY/MM/DD/filename
    return f'data_enrichment/inputs/{instance.company_id}/{timezone.now().strftime("%Y/%m/%d")}/{instance.id}/{filename}'

def upload_as_output_file(instance, filename):
    # Files will be uploaded to MEDIA_ROOT/data_files/YYYY/MM/DD/filename
    return f'data_enrichment/outputs/{instance.company_id}/{timezone.now().strftime("%Y/%m/%d")}/{instance.id}/{filename}'


class DataEnrichmentPartition(CompanyBaseModel):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
    ]

    request = models.ForeignKey(
        'DataEnrichment',
        on_delete=models.CASCADE,
        related_name='partitions',
        help_text='Data Enrichment request this partition belongs to'
    )
    input_file_path = models.CharField(
        max_length=500,
        help_text='Path to the input partition file'
    )
    output_file_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Path to the output partition file'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text='Current status of the partition'
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this partition was processed'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text='Error message if processing failed'
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text='Additional metadata about the partition'
    )

    def __str__(self):
        return f"Partition {self.id} for request {self.request_id}"

    def get_input_file_url(self):
        """Get URL for input file"""
        if self.input_file_path:
            return f"/media/{self.input_file_path}"
        return None

    def get_output_file_url(self):
        """Get URL for output file"""
        if self.output_file_path:
            return f"/media/{self.output_file_path}"
        return None

    class Meta:
        db_table = 'data_processing_data_enrichment_partition'
        verbose_name = "Data Enrichment Partition"
        verbose_name_plural = "Data Enrichment Partitions"
        ordering = ['created_at']


class DataEnrichment(CompanyBaseModel):

    LLM_MODEL_CHOICE_OLLAMA_MISTRAL = 'ollama_mistral'
    LLM_MODEL_CHOICE_OPENAI_GPT_3_5 = 'openai_gpt_3_5'
    LLM_MODEL_CHOICE_VERTEX_AI_MISTRAL = 'vertex_ai_mistral'
    LLM_MODEL_CHOICE_VERTEX_AI_GEMINI_1_5_FLASH = 'vertex_ai_gemini_1_5_flash'

    LLM_MODEL_CHOICES = [
        (LLM_MODEL_CHOICE_OLLAMA_MISTRAL, 'Ollama: Mistral'),
        (LLM_MODEL_CHOICE_OPENAI_GPT_3_5, 'OpenAI: GPT-3.5'),
        (LLM_MODEL_CHOICE_VERTEX_AI_MISTRAL, 'Vertex AI: Mistral'),
        (LLM_MODEL_CHOICE_VERTEX_AI_GEMINI_1_5_FLASH, 'Vertex AI: Gemini 1.5 Flash'),
    ]
    
    STATUS_PENDING = 'pending'
    STATUS_PARTITION_CREATED = 'partition_created'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PARTITION_CREATED, 'Partitions Created'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
    ]
    session_id = models.CharField(
    max_length=36,  # UUID length
    unique=True,
    default=UUID.get_uuid,
    editable=False,
    null=True,
    blank=True,
    help_text='Unique session identifier for this enrichment request'
)
    name = models.CharField(max_length=200, default='Data Enrichment', verbose_name='Name', help_text='Name of the Data Enrichment request')
    input_file = models.FileField(upload_to=upload_as_input_file)
    output_file = models.FileField(upload_to=upload_as_output_file, null=True, blank=True)
    prompt = models.CharField(max_length=200)
    llm_model = models.CharField(
        max_length=30,
        choices=LLM_MODEL_CHOICES,
        default=LLM_MODEL_CHOICE_OLLAMA_MISTRAL,
        verbose_name='LLM Model'
    )
    batch_size = models.IntegerField(default=100)
    file_size = models.IntegerField(null=True, blank=True, help_text='File Size In MB')
    completion_percentage = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Status'
    )
    combine_output_files = models.BooleanField(default=False, 
                                               help_text='Combine output files into a single file')
    parallel_threading_count = models.IntegerField(default=1)
    status_metadata = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    processing_error = models.TextField(null=True, blank=True)
    execution_start_at = models.DateTimeField(null=True, blank=True)
    execution_end_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.prompt} - {self.status}"

    def get_execution_time(self):
        """Calculate total execution time in seconds"""
        if self.execution_start_at and self.execution_end_at:
            return (self.execution_end_at - self.execution_start_at).total_seconds()
        return 0

    def get_execution_time_display(self):
        """Get human-readable execution time"""
        seconds = self.get_execution_time()
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if remaining_seconds > 0 or not parts:
            parts.append(f"{remaining_seconds}s")
            
        return " ".join(parts)

    def get_status_display_with_percentage(self):
        """Get status with completion percentage if processing"""
        # Get partition counts
        total_partitions = self.get_total_partitions_count()
        if total_partitions == 0:
            return self.get_status_display()
            
        processed = self.get_processed_partitions_count()
        failed = self.get_failed_partitions_count()
        total_processed = processed + failed
        
        # Calculate completion percentage
        completion_percentage = int((total_processed / total_partitions) * 100)
        
        # Determine status based on partition data
        if total_processed == total_partitions:
            if failed == 0:
                new_status = self.STATUS_DONE
            elif processed == 0:
                new_status = self.STATUS_ERROR
            else:
                new_status = self.STATUS_DONE
        elif total_processed > 0:
            new_status = self.STATUS_PROCESSING
        else:
            new_status = self.status
            
        # Update request if status has changed
        if new_status != self.status or completion_percentage != self.completion_percentage:
            self.__class__.objects.filter(id=self.id).update(
                status=new_status,
                completion_percentage=completion_percentage,
                status_metadata={
                    "total_partitions": total_partitions,
                    "processed_partitions": processed,
                    "failed_partitions": failed,
                    "pending_partitions": total_partitions - total_processed,
                    "completion_percentage": completion_percentage,
                    "last_updated": timezone.now().isoformat()
                }
            )
            # Update instance attributes
            self.status = new_status
            self.completion_percentage = completion_percentage
            
        # Return formatted status string
        status = self.get_status_display()
        if new_status == self.STATUS_PROCESSING:
            return f"{status} ({completion_percentage}%)"
        return status

    def get_processed_partitions_count(self):
        """Get count of successfully processed partitions"""
        return self.partitions.filter(status=DataEnrichmentPartition.STATUS_DONE).count()

    def get_total_partitions_count(self):
        """Get total number of partitions"""
        return self.partitions.count()

    def get_failed_partitions_count(self):
        """Get count of failed partitions"""
        return self.partitions.filter(status=DataEnrichmentPartition.STATUS_ERROR).count()

    def get_partition_status_summary(self):
        """Get a summary of partition processing status"""
        total = self.get_total_partitions_count()
        processed = self.get_processed_partitions_count()
        failed = self.get_failed_partitions_count()
        pending = self.partitions.filter(status=DataEnrichmentPartition.STATUS_PENDING).count()
        processing = self.partitions.filter(status=DataEnrichmentPartition.STATUS_PROCESSING).count()
        
        status_parts = []
        if processed > 0:
            status_parts.append(f"{processed} processed")
        if failed > 0:
            status_parts.append(f"{failed} failed")
        if pending > 0:
            status_parts.append(f"{pending} pending")
        if processing > 0:
            status_parts.append(f"{processing} processing")
            
        status_text = ", ".join(status_parts) if status_parts else "No partitions"
        return f"{status_text} (Total: {total})"

    def get_file_status_info(self):
        """Get detailed file status information for admin display"""
        if not self.status_metadata:
            return []
        
        status_info = []
        for partition in self.status_metadata:
            info = {
                'input_file': partition.get('input_file_name', ''),
                'output_file': partition.get('output_file_name', ''),
                'is_processed': partition.get('is_processed', False),
                'processed_at': partition.get('processed_at', ''),
                'error': partition.get('error', ''),
                'start_row': partition.get('start_row', 0),
                'end_row': partition.get('end_row', 0),
                'total_rows': partition.get('total_rows', 0)
            }
            status_info.append(info)
        return status_info

    def input_file_size(self):
        """Get input file size in human-readable format"""
        if not self.input_file:
            return '-'
        
        try:
            size_bytes = self.input_file.size
            
            if size_bytes < 1024:  # Less than 1KB
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:  # Less than 1MB
                return f"{size_bytes/1024:.2f} KB"
            elif size_bytes < 1024 * 1024 * 1024:  # Less than 1GB
                return f"{size_bytes/(1024*1024):.2f} MB"
            else:
                return f"{size_bytes/(1024*1024*1024):.2f} GB"
        except Exception:
            return '-'
            
    input_file_size.short_description = 'Input Size'

    def get_input_file_url(self):
        """Get URL for input file"""
        if self.input_file:
            return f"/media/{self.input_file.name}"
        return None

    def get_output_file_url(self):
        """Get URL for output file"""
        if self.output_file:
            return f"/media/{self.output_file.name}"
        return None

    def reset_partition_stats(self):
        """Reset all partition stats for this request"""
        try:
            # Check if request is currently being processed
            if self.status == DataEnrichment.STATUS_PROCESSING:
                raise ValueError(f"Cannot reset request while it is being processed. {5} partitions are currently being processed in parallel. Please wait for processing to complete or fail.")

            # Get current partition counts for metadata
            total_partitions = self.partitions.count()
            partition_ids = list(self.partitions.values_list('id', flat=True))

            # Reset all partitions to pending
            self.partitions.all().update(
                status=DataEnrichmentPartition.STATUS_PENDING,
                processed_at=None,
                error_message=None,
                metadata={
                    "reset_at": timezone.now().isoformat(),
                    "previous_status": self.status,
                    "request_id": str(self.id),
                    "session_id": self.session_id,
                    "parallel_execution_count": 5  # From memory: PARALLEL_EXECUTION_COUNT
                }
            )
            
            # Update request status and metadata
            self.status = DataEnrichment.STATUS_PARTITION_CREATED
            self.completion_percentage = 0
            self.execution_start_at = None
            self.execution_end_at = None
            self.processing_error = None
            
            # Update status metadata with parallel processing info
            self.status_metadata = {
                "reset_at": timezone.now().isoformat(),
                "total_partitions": total_partitions,
                "request_id": str(self.id),
                "session_id": self.session_id,
                "parallel_execution_count": 5,  # From memory: PARALLEL_EXECUTION_COUNT
                "processed_partitions": [],
                "failed_partitions": [],
                "pending_partitions": partition_ids
            }
            
            self.save()

            # Return summary for admin message
            return {
                "total": total_partitions,
                "status": self.status,
                "parallel_execution_count": 5  # From memory: PARALLEL_EXECUTION_COUNT
            }

        except Exception as e:
            # Log the error and preserve the state for debugging
            error_msg = f"Failed to reset partitions: {str(e)}"
            self.processing_error = error_msg
            self.status = DataEnrichment.STATUS_ERROR
            self.save()
            raise ValueError(error_msg)

    class Meta:
        db_table = 'data_processing_data_enrichment'
        verbose_name = "Data Enrichment Request"
        verbose_name_plural = "Data Enrichment Requests"
        ordering = ['-created_at']

class DataIngestionPartition(CompanyBaseModel):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
    ]

    request = models.ForeignKey(
        'DataIngestion',
        on_delete=models.CASCADE,
        related_name='partitions',
        help_text='Data Ingestion request this partition belongs to'
    )
    input_file_path = models.CharField(
        max_length=500,
        help_text='Path to the input partition file'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text='Current status of the partition'
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this partition was processed'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text='Error message if processing failed'
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text='Additional metadata about the partition'
    )
        
    def __str__(self):
        return f"Partition {self.id} for request {self.request_id}"

    def get_input_file_url(self):
        """Get URL for input file"""
        if self.input_file_path:
            return f"/media/{self.input_file_path}"
        return None

    class Meta:
        db_table = 'data_processing_data_ingestion_partition'
        verbose_name = "Data Ingestion Partition"
        verbose_name_plural = "Data Ingestion Partitions"
        ordering = ['created_at']

class DataIngestion(CompanyBaseModel):
    """Model to store data ingestion jobs"""
    STATUS_INITIATED = 'initiated'
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'
    STATUS_DATA_INGESTED = 'data_ingested'
    STATUS_EMBEDDING_GENERATED = 'embedding_generated'

    STATUS_CHOICES = [
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
        (STATUS_DATA_INGESTED, 'Ingested'),
        (STATUS_EMBEDDING_GENERATED, 'Embedding Generated')
    ]

    CHUNKING_STATUS_COMPLETED = 'completed'
    CHUNKING_STATUS_PROCESSING = 'processing'
    CHUNKING_STATUS_PENDING = 'pending'

    CHUNKING_STATUS_CHOICES = [
        (CHUNKING_STATUS_COMPLETED, 'Completed'),
        (CHUNKING_STATUS_PROCESSING, 'Processing'),
        (CHUNKING_STATUS_PENDING, 'Pending'),
    ]
    
    EXECUTION_TYPE_WORKFLOW = 'workflow'

    EXECUTION_TYPE_PROMPT = 'prompt'
    EXECUTION_TYPE_CHOICES = [
        (EXECUTION_TYPE_WORKFLOW, 'Workflow'),
        (EXECUTION_TYPE_PROMPT, 'Prompt'),
    ]

    SCHEMA_TYPE_DEFINED = 'defined'
    SCHEMA_TYPE_CREATE = 'create'
    SCHEMA_TYPE_CHOICES = [
        (SCHEMA_TYPE_DEFINED, 'Prompt with schema'),
        (SCHEMA_TYPE_CREATE, 'Prompt to generate schema'),
    ]

    DESTINATION_NEO4J = 'neo4j'
    DESTINATION_PINECONE = 'pinecone'
    DESTINATION_TYPE_CHOICES = [
        (DESTINATION_NEO4J, 'Neo4j'),
        (DESTINATION_PINECONE, 'Pinecone'),
    ]
    
    session_id = models.CharField(
        max_length=36,
        unique=True,
        default=UUID.get_uuid,
        editable=False,
        null=True,
        blank=True,
        help_text='Unique session identifier for this ingestion request'
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='ingestion_files/', null=True, blank=True)
    execution_type = models.CharField(max_length=10, choices=EXECUTION_TYPE_CHOICES, default=EXECUTION_TYPE_PROMPT)
    workflow = models.CharField(max_length=100, blank=True, null=True, help_text=_("API Controller to use if execution type is workflow"))
    prompt_name = models.CharField(max_length=100, blank=True, null=True, help_text=_("Langfuse prompt name to use if execution type is prompt"))
    schema_type = models.CharField(max_length=10, choices=SCHEMA_TYPE_CHOICES, default=SCHEMA_TYPE_DEFINED)
    prompt_defined_schema = models.CharField(max_length=100, blank=True, null=True, help_text=_("Prompt with the defined schema"))
    prompt_create_schema = models.CharField(max_length=100, blank=True, null=True, help_text=_("Prompt used to create schema using LLM"))
    chunk_size = models.PositiveIntegerField(help_text=_("Number of objects/rows/tokens depending on file type"), blank=True, null=True)
    chunk_overlap = models.PositiveIntegerField(default=0, blank=True, null=True, help_text=_("Overlap between chunks (for text files)"))
    destination = models.CharField(max_length = 25, choices=DESTINATION_TYPE_CHOICES, default=DESTINATION_NEO4J)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    chunking_status = models.CharField(max_length=20, choices=CHUNKING_STATUS_CHOICES, default=CHUNKING_STATUS_COMPLETED)
    completion_percentage = models.PositiveIntegerField(default=0)
    status_metadata = models.JSONField(null=True, blank=True)
    processing_error = models.TextField(blank=True)
    execution_start_at = models.DateTimeField(null=True, blank=True)
    execution_end_at = models.DateTimeField(null=True, blank=True)
    is_valid_embedding = models.BooleanField(default=False)
    generate_embedding = models.BooleanField(default=False)
    embedding_generated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def get_execution_time(self):
        """Calculate total execution time in seconds"""
        if self.execution_start_at and self.execution_end_at:
            return (self.execution_end_at - self.execution_start_at).total_seconds()
        return 0

    def get_execution_time_display(self):
        """Get human-readable execution time"""
        seconds = self.get_execution_time()
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if remaining_seconds > 0 or not parts:
            parts.append(f"{remaining_seconds}s")
            
        return " ".join(parts)

    
    def get_status_display_with_percentage(self):
        """Get status with completion percentage if processing"""
        # Get partition counts
        total_partitions = self.get_total_partitions_count()
        if total_partitions == 0:
            return self.get_status_display()
            
        processed = self.get_processed_partitions_count()
        failed = self.get_failed_partitions_count()
        total_processed = processed + failed
        
        # Calculate completion percentage
        completion_percentage = int((total_processed / total_partitions) * 100)
        
        # Determine status based on partition data
        if total_processed == total_partitions:
            if failed == 0:
                new_status = self.STATUS_DONE
            elif processed == 0:
                new_status = self.STATUS_ERROR
            else:
                new_status = self.STATUS_DONE
        elif total_processed > 0:
            new_status = self.STATUS_PROCESSING
        else:
            new_status = self.status
            
        # Update request if status has changed
        if new_status != self.status or completion_percentage != self.completion_percentage:
            self.__class__.objects.filter(id=self.id).update(
                status=new_status,
                completion_percentage=completion_percentage,
                status_metadata={
                    "total_partitions": total_partitions,
                    "processed_partitions": processed,
                    "failed_partitions": failed,
                    "pending_partitions": total_partitions - total_processed,
                    "completion_percentage": completion_percentage,
                    "last_updated": timezone.now().isoformat()
                }
            )
            # Update instance attributes
            self.status = new_status
            self.completion_percentage = completion_percentage
            
        # Return formatted status string
        status = self.get_status_display()
        if new_status == self.STATUS_PROCESSING:
            return f"{status} ({completion_percentage}%)"
        return status

    def get_processed_partitions_count(self):
        """Get count of successfully processed partitions"""
        return self.partitions.filter(status=self.STATUS_DONE).count()

    def get_total_partitions_count(self):
        """Get total number of partitions"""
        return self.partitions.count()

    def get_failed_partitions_count(self):
        """Get count of failed partitions"""
        return self.partitions.filter(status=self.STATUS_ERROR).count()

    def get_partition_status_summary(self):
        """Get a summary of partition processing status"""
        total = self.get_total_partitions_count()
        processed = self.get_processed_partitions_count()
        failed = self.get_failed_partitions_count()
        pending = self.partitions.filter(status=self.STATUS_PENDING).count()
        processing = self.partitions.filter(status=self.STATUS_PROCESSING).count()
        
        status_parts = []
        if processed > 0:
            status_parts.append(f"{processed} processed")
        if failed > 0:
            status_parts.append(f"{failed} failed")
        if pending > 0:
            status_parts.append(f"{pending} pending")
        if processing > 0:
            status_parts.append(f"{processing} processing")
            
        status_text = ", ".join(status_parts) if status_parts else "No partitions"
        return f"{status_text} (Total: {total})"

    def reset_partition_stats(self):
        """Reset all partition stats for this request"""
        try:
            # Check if request is currently being processed
            if self.status == self.STATUS_PROCESSING:
                raise ValueError(f"Cannot reset request while it is being processed. {5} partitions are currently being processed in parallel. Please wait for processing to complete or fail.")

            # Get current partition counts for metadata
            total_partitions = self.partitions.count()
            partition_ids = list(self.partitions.values_list('id', flat=True))

            # Reset all partitions to pending
            self.partitions.all().update(
                status='pending',
                processed_at=None,
                error_message=None,
                metadata={
                    "reset_at": timezone.now().isoformat(),
                    "previous_status": self.status,
                    "request_id": str(self.id),
                    "parallel_execution_count": 5  # From memory: PARALLEL_EXECUTION_COUNT
                }
            )
            
            # Update request status and metadata
            self.status = self.STATUS_PENDING
            self.completion_percentage = 0
            self.execution_start_at = None
            self.execution_end_at = None
            self.processing_error = ""
            
            # Update status metadata with parallel processing info
            self.status_metadata = {
                "reset_at": timezone.now().isoformat(),
                "total_partitions": total_partitions,
                "request_id": str(self.id),
                "parallel_execution_count": 5,  # From memory: PARALLEL_EXECUTION_COUNT
                "processed_partitions": [],
                "failed_partitions": [],
                "pending_partitions": partition_ids
            }
            
            self.save()

            # Return summary for admin message
            return {
                "total": total_partitions,
                "status": self.status,
                "parallel_execution_count": 5  # From memory: PARALLEL_EXECUTION_COUNT
            }

        except Exception as e:
            # Log the error and preserve the state for debugging
            error_msg = f"Failed to reset partitions: {str(e)}"
            self.processing_error = error_msg
            self.status = self.STATUS_ERROR
            self.save()
            raise ValueError(error_msg)
        
class DataEmbedding(CompanyBaseModel):
    """Model to store data embedding jobs"""
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_ERROR, 'Error'),
    ]

    name = models.CharField(max_length=255)
    batch_size = models.PositiveIntegerField(default=50, help_text='Number of nodes to process in a batch')
    max_label_workers = models.PositiveIntegerField(default=3, help_text='Maximum number of labels to process in parallel')
    max_batch_workers = models.PositiveIntegerField(default=3, help_text='Maximum number of batches to process in parallel per label')
    
    labels = models.JSONField(default=list, blank=True, null=True, 
                                help_text='List of node labels to process')
    selected_properties = models.JSONField(default=dict, blank=True, null=True, 
                                help_text='Dictionary mapping labels to their selected properties with embedding field names') 
    embedding_groups = models.JSONField(default=dict, blank=True, null=True,
                                help_text='Configuration of embedding groups per label')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    completion_percentage = models.PositiveIntegerField(default=0)
    nodes_processed = models.PositiveIntegerField(default=0)
    embeddings_generated = models.PositiveIntegerField(default=0)
    total_processing_time = models.FloatField(default=0, help_text='Total processing time in seconds')
    status_metadata = models.JSONField(null=True, blank=True)
    processing_error = models.TextField(blank=True)
    execution_start_at = models.DateTimeField(null=True, blank=True)
    execution_end_at = models.DateTimeField(null=True, blank=True)
    is_valid_embedding = models.BooleanField(default=False)    
    
    
    session_id = models.CharField(
        max_length=36,
        unique=True,
        default=UUID.get_uuid,
        editable=False,
        null=True,
        blank=True,
        help_text='Unique session identifier for this embedding request'
    )

    def __str__(self):
        return self.name

    def get_execution_time(self):
        """Calculate total execution time in seconds"""
        if self.execution_start_at and self.execution_end_at:
            return (self.execution_end_at - self.execution_start_at).total_seconds()
        return 0

    def get_execution_time_display(self):
        """Get human-readable execution time"""
        seconds = self.get_execution_time()
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if remaining_seconds > 0 or not parts:
            parts.append(f"{remaining_seconds}s")
            
        return " ".join(parts)

    class Meta:
        db_table = 'data_processing_data_embedding'
        verbose_name = "Data Embedding"
        verbose_name_plural = "Data Embeddings"
        ordering = ['-created_at']