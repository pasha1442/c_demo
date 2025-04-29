import os
import json
from django.conf import settings
from django.utils import timezone
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd
from data_processing.states.ingestion_metadata_state import IngestionMetadataState
from data_processing.models import DataIngestionPartition

class FileChunker:
    """
    A class to handle file chunking for different file types and save chunks to disk
    with proper metadata tracking.
    """
    
    def __init__(self, ingestion_job):
        """
        Initialize the file chunker with an ingestion job
        
        Args:
            ingestion_job: DataIngestion model instance
        """
        self.ingestion_job = ingestion_job
        self.file_path = ingestion_job.file.path
        self.file_name = os.path.basename(ingestion_job.file.name)
        self.file_extension = self.file_name.split('.')[-1].lower()
        self.chunk_size = ingestion_job.chunk_size
        self.chunk_overlap = ingestion_job.chunk_overlap or 0
        
        # Create directory structure for processed outputs only
        timestamp = timezone.now().strftime("%Y/%m/%d")
        company_id = str(ingestion_job.company_id) if hasattr(ingestion_job, 'company_id') else 'default'
        
        self.output_dir = os.path.join(
            settings.MEDIA_ROOT, 
            'ingestion_files', 
            'chunks',
            company_id,
            str(ingestion_job.id)
        )
        
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"Initialized FileChunker for file: {self.file_name}, extension: {self.file_extension}")
        print(f"Output directory created at: {self.output_dir}")
    
    def _update_metadata(self, stage: str, status: str) -> None:
        """Update the pipeline metadata state for a specific stage."""
        if isinstance(self.ingestion_job.status_metadata, dict):
            metadata_state = IngestionMetadataState.from_dict(self.ingestion_job.status_metadata)
            metadata_state.update_pipeline_stage(stage, status)
            self.ingestion_job.status_metadata = metadata_state.to_dict()
            self.ingestion_job.save()

    def process_file(self):
        """
        Process the file based on its extension and create partitions
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update pipeline status
            self._update_metadata('chunking', 'in_progress')
            
            print(f"Processing file {self.file_name} (type: {self.file_extension}) for job {self.ingestion_job.id}")
            print(f"Chunk size: {self.chunk_size}, Chunk overlap: {self.chunk_overlap}")
            
            # Select chunking method based on file extension
            if self.file_extension == 'json':
                self._process_json_file()
            elif self.file_extension in ['csv', 'tsv']:
                self._process_csv_file()
            elif self.file_extension in ['txt', 'md', 'html', 'xml', 'pdf']:
                self._process_text_file()
            else:
                error_msg = f"Unsupported file extension: {self.file_extension}"
                self.ingestion_job.processing_error = error_msg
                self.ingestion_job.status = self.ingestion_job.STATUS_ERROR
                
                # Update pipeline status to error
                self._update_metadata('chunking', 'failed')
                print(f"ERROR: {error_msg}")
                return False
            
            # Count the number of partitions created
            partitions_count = self.ingestion_job.partitions.count()
            print(f"Created {partitions_count} partitions for file {self.file_name}")
            
            # Update pipeline status to completed for chunking stage
            self._update_metadata('chunking', 'completed')
            
            # Update total completion percentage
            self.ingestion_job.completion_percentage = 10  # Chunking complete - 10%
            self.ingestion_job.save()
            print(f"Updated completion percentage to 10% - Chunking complete")
            
            return True
            
        except Exception as e:
            error_msg = f"Error processing file {self.file_name}: {str(e)}"
            self.ingestion_job.processing_error = error_msg
            self.ingestion_job.status = self.ingestion_job.STATUS_ERROR
            
            # Update pipeline status to error
            self._update_metadata('chunking', 'failed')
            print(f"EXCEPTION: {error_msg}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _process_json_file(self):
        """Process and chunk a JSON file"""
        print(f"Chunking JSON file: {self.file_path}, chunk size: {self.chunk_size}")
        
        with open(self.file_path, 'r') as f:
            data = json.load(f)
        
        # Extract items from JSON structure
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and any(isinstance(v, list) for v in data.values()):
            for key, value in data.items():
                if isinstance(value, list):
                    items = value
                    break
            else:
                items = [data]
        else:
            items = [data]
        
        total_chunks = (len(items) + self.chunk_size - 1) // self.chunk_size
        print(f"Found {len(items)} items, will create {total_chunks} chunks")
        
        for i in range(0, len(items), self.chunk_size):
            chunk_number = i // self.chunk_size + 1
            chunk = items[i:i+self.chunk_size]
            print(f"Creating JSON chunk {chunk_number}/{total_chunks} with {len(chunk)} items")
            
            # Create chunk file
            self._save_json_chunk(chunk, chunk_number, total_chunks)
    
    def _process_csv_file(self):
        """Process and chunk a CSV file"""
        print(f"Chunking CSV file: {self.file_path}, chunk size: {self.chunk_size}")
        
        # Read the CSV file with pandas
        df = pd.read_csv(self.file_path)
        total_rows = len(df)
        total_chunks = (total_rows + self.chunk_size - 1) // self.chunk_size
        
        print(f"Found {total_rows} rows, will create {total_chunks} chunks")
        print(f"CSV columns: {', '.join(df.columns.tolist())}")
        
        # Create chunks
        for i in range(total_chunks):
            start_idx = i * self.chunk_size
            end_idx = min((i + 1) * self.chunk_size, total_rows)
            chunk_df = df.iloc[start_idx:end_idx]
            print(f"Creating CSV chunk {i+1}/{total_chunks} with rows {start_idx} to {end_idx}")
            
            # Create chunk file
            self._save_csv_chunk(chunk_df, i+1, total_chunks, start_idx, end_idx)
    
    def _process_text_file(self):
        """Process and chunk a text file"""
        print(f"Chunking text file: {self.file_path}, chunk size: {self.chunk_size}, overlap: {self.chunk_overlap}")
        
        with open(self.file_path, 'r') as f:
            text = f.read()
        
        print(f"Text file size: {len(text)} characters")
        
        # Use LangChain's text splitter for text files
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
        )
        
        chunks = text_splitter.split_text(text)
        total_chunks = len(chunks)
        
        print(f"Created {total_chunks} text chunks")
        
        # Save each chunk
        for i, chunk_text in enumerate(chunks):
            print(f"Processing text chunk {i+1}/{total_chunks}, size: {len(chunk_text)} characters")
            self._save_text_chunk(chunk_text, i+1, total_chunks)


    
    def _save_json_chunk(self, chunk_data, chunk_number, total_chunks):
        """Save JSON chunk to file and create a partition record"""
        output_filename = f'chunk_{chunk_number}_output.json'
        output_filepath = os.path.join(self.output_dir, output_filename)
        
        try:
            # Write the chunk data to a file
            with open(output_filepath, 'w') as f:
                json.dump(chunk_data, f, indent=2)
            
            print(f"Saved JSON chunk file to: {output_filepath}")
            
            # Create partition record with detailed metadata
            partition = DataIngestionPartition.objects.create(
                request=self.ingestion_job,
                input_file_path=os.path.relpath(output_filepath, settings.MEDIA_ROOT),
                status=DataIngestionPartition.STATUS_PENDING,
                metadata={
                    'chunk_number': chunk_number,
                    'total_chunks': total_chunks,
                    'items_count': len(chunk_data),
                    'start_index': (chunk_number - 1) * self.chunk_size,
                    'end_index': (chunk_number - 1) * self.chunk_size + len(chunk_data),
                    'output_file_name': output_filename,
                    'created_at': timezone.now().isoformat(),
                    'file_type': 'json'
                }
            )
            
            print(f"Created partition record {partition.id} for JSON chunk {chunk_number} of {total_chunks}")
            return partition
            
        except Exception as e:
            error_msg = f"Error creating JSON chunk for chunk {chunk_number}: {str(e)}"
            print(f"EXCEPTION: {error_msg}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _save_csv_chunk(self, chunk_df, chunk_number, total_chunks, start_idx, end_idx):
        """Save CSV chunk to file and create a partition record"""
        output_filename = f'chunk_{chunk_number}_output.json'
        output_filepath = os.path.join(self.output_dir, output_filename)
        
        try:
            # Convert chunk data to a serializable format
            chunk_records = json.loads(chunk_df.to_json(orient='records'))
            
            # Write the chunk data to a file
            with open(output_filepath, 'w') as f:
                json.dump(chunk_records, f, indent=2)
            
            print(f"Saved CSV chunk file to: {output_filepath}")
            
            # Create partition record with detailed metadata
            partition = DataIngestionPartition.objects.create(
                request=self.ingestion_job,
                input_file_path=os.path.relpath(output_filepath, settings.MEDIA_ROOT),
                status=DataIngestionPartition.STATUS_PENDING,
                metadata={
                    'chunk_number': chunk_number,
                    'total_chunks': total_chunks,
                    'start_row': start_idx,
                    'end_row': end_idx,
                    'rows_count': len(chunk_df),
                    'output_file_name': output_filename,
                    'created_at': timezone.now().isoformat(),
                    'columns': chunk_df.columns.tolist(),
                    'file_type': 'csv'
                }
            )
            
            print(f"Created partition record {partition.id} for CSV chunk {chunk_number} of {total_chunks}")
            return partition
            
        except Exception as e:
            error_msg = f"Error creating CSV chunk for chunk {chunk_number}: {str(e)}"
            print(f"EXCEPTION: {error_msg}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _save_text_chunk(self, chunk_text, chunk_number, total_chunks):
        """Save text chunk to file and create a partition record"""
        output_filename = f'chunk_{chunk_number}_output.json'
        output_filepath = os.path.join(self.output_dir, output_filename)
        
        try:
            # Write the chunk data to a file
            with open(output_filepath, 'w') as f:
                json.dump({"text": chunk_text}, f, indent=2)
            
            print(f"Saved text chunk file to: {output_filepath}")
            
            # Create partition record with detailed metadata
            partition = DataIngestionPartition.objects.create(
                request=self.ingestion_job,
                input_file_path=os.path.relpath(output_filepath, settings.MEDIA_ROOT),
                status=DataIngestionPartition.STATUS_PENDING,
                metadata={
                    'chunk_number': chunk_number,
                    'total_chunks': total_chunks,
                    'characters_count': len(chunk_text),
                    'output_file_name': output_filename,
                    'created_at': timezone.now().isoformat(),
                    'file_type': 'text'
                }
            )
            
            print(f"Created partition record {partition.id} for text chunk {chunk_number} of {total_chunks}")
            return partition
            
        except Exception as e:
            error_msg = f"Error creating text chunk for chunk {chunk_number}: {str(e)}"
            print(f"EXCEPTION: {error_msg}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise