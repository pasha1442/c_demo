import asyncio
import json
import csv
import io
import os
import traceback
from neo4j import AsyncGraphDatabase
from django.utils import timezone
from chat.assistants import get_active_prompt_from_langfuse
from company.models import CompanySetting
from data_processing.file_chunker import FileChunker
from backend.services.langfuse_service import LangfuseService
from data_processing.models import DataIngestion, DataIngestionPartition
from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
import re
from backend.logger import Logger
import aiofiles
from typing import List, Dict, Tuple, Any, Optional, Union
from functools import wraps
import time

# Configure logger
logger = Logger(Logger.INFO_LOG)

class AsyncDataIngestionService:
    """
    Asynchronous service for handling data ingestion into Neo4j graph database.
    Uses asyncio to process chunks in parallel for better performance.
    
    Main improvements over synchronous version:
    1. Parallel chunk processing with controlled concurrency
    2. Non-blocking file I/O operations
    3. Asynchronous Neo4j operations
    4. Non-blocking database model updates
    5. Performance metrics and timing built-in
    """
    """
    Asynchronous service for handling data ingestion into Neo4j graph database.
    Uses asyncio to process chunks in parallel for better performance.
    """
    
    def __init__(self, ingestion_job: DataIngestion=None, max_concurrent_tasks: int = 5):
        """
        Initialize the AsyncDataIngestionService
        
        Args:
            ingestion_job: The DataIngestion model instance
            max_concurrent_tasks: Maximum number of concurrent processing tasks
        """
        self.supported_file_types = {
            'json': 'application/json',
            'csv': 'text/csv',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'html': 'text/html',
            'xml': 'application/xml',
            'pdf': 'application/pdf'
        }
        self.NEW_SCHEMA_PROMPT_NAME = "schema_generator"
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.company = ingestion_job.company
        self.current_ingestion_job = ingestion_job
        
    def async_timer(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            logger.add(f"Starting {func.__name__}")
            result = await func(self, *args, **kwargs)
            elapsed = time.time() - start_time
            logger.add(f"Completed {func.__name__} in {elapsed:.2f} seconds")
            return result
        return wrapper
        
    async def _initialize_ingestion_metadata(self, ingestion_job: DataIngestion):
        """Prepare ingestion job metadata asynchronously."""
        if (ingestion_job.status == DataIngestion.STATUS_PENDING):
            ingestion_job.execution_start_at = timezone.now()
            ingestion_job.status = DataIngestion.STATUS_PROCESSING
            await self._async_save_model(ingestion_job)
        
        self.langfuse_service = LangfuseService(ingestion_job.company_id)

    async def _async_save_model(self, model):
        """Save Django model asynchronously"""
        # Use a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, model.save)
        
    async def _async_db_operation(self, operation):
        """Execute a database operation asynchronously
        
        Args:
            operation: A lambda or function that performs a database operation
            
        Returns:
            The result of the database operation
        """
        # Use a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, operation)
    
    @async_timer
    async def process_ingestion_job(self, ingestion_job: DataIngestion) -> bool:
        """
        Process a data ingestion job asynchronously
        
        Args:
            ingestion_job: The DataIngestion model instance to process

        Returns:
            bool: True if successful, False otherwise
        """
        # Store reference to current ingestion job for error handling
        self.current_ingestion_job = ingestion_job
        
        try:
            await self._initialize_ingestion_metadata(ingestion_job)
            # Update completion percentage based on existing partitions
            await self._update_completion_from_partitions(ingestion_job)
            
            # Process schema generation
            schema = await self._process_schema_generation(ingestion_job)
            if not schema:
                logger.add("Schema generation failed")
                return False

            # Validate file extension
            file_extension = ingestion_job.file.name.split('.')[-1].lower()
            logger.add(f"Processing file with extension: {file_extension}")

            chunking_status = ingestion_job.chunking_status
            logger.add(f"Current chunking status: {chunking_status}")
            
            if chunking_status == DataIngestion.CHUNKING_STATUS_PENDING:
                if file_extension not in self.supported_file_types:
                    error_msg = f"Unsupported file type: {file_extension}"
                    return False
                
                ingestion_job.chunking_status = DataIngestion.CHUNKING_STATUS_PROCESSING
                await self._async_save_model(ingestion_job)
                
                # Process file chunking
                logger.add("Starting file chunking process")
                try:
                    chunker = FileChunker(ingestion_job)
                    chunking_result = await self._async_process_file(chunker)
                    if not chunking_result:
                        error_msg = "File chunking failed"
                        return False
                except Exception as chunk_error:
                    error_msg = f"File chunking failed with error: {str(chunk_error)}"
                    stack_trace = traceback.format_exc()
                    return False
                logger.add("File chunking completed successfully")

                await self._update_completion_from_partitions(ingestion_job)

            else:
                logger.add("Chunking already complete, moving forward")
            
            # Process based on execution type
            if ingestion_job.execution_type == ingestion_job.EXECUTION_TYPE_WORKFLOW:
                # will add later
                logger.add("Workflow execution not yet implemented")
                return False
            elif ingestion_job.execution_type == ingestion_job.EXECUTION_TYPE_PROMPT:
                return await self._process_with_prompt(ingestion_job)
            else:
                error_msg = f"Unknown execution type: {ingestion_job.execution_type}"
                return False

        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e)}"
            stack_trace = traceback.format_exc()
            logger.add(error_msg)
            logger.add(stack_trace)
            return False
    
    async def _async_process_file(self, chunker):
        """Run file chunking in a thread pool to avoid blocking the event loop"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, chunker.process_file)
        return result
    
    @async_timer
    async def _process_schema_generation(self, ingestion_job: DataIngestion):
        schema = {}
        stage = 'schema_generation'
        try:
            if ingestion_job.schema_type == "defined":
                schema = await self._get_defined_schema(ingestion_job)
                if not schema:
                    # await self._update_metadata(ingestion_job, stage, 'failed')
                    logger.add("Schema not provided in selected prompt")
            else:
                driver = await self._setup_neo4j_connection()
                schema = await self._get_neo4j_schema(driver)

                if not schema:
                    schema = await self._create_new_schema(ingestion_job)
                    if not schema:
                        logger.add("Schema generation Failed")
                        return
            
            return schema
        
        except Exception as e:
            error_message = f"Error in schema generation: {str(e)}"
            stack_trace = traceback.format_exc()
            await self._log_error(ingestion_job, 
                          error_message, 
                          "schema_generation", 
                          error_type="generation", 
                          is_fatal=True, 
                          stack_trace=stack_trace)
            await self._update_metadata(ingestion_job, 'schema_generation', 'failed')
            logger.add(f"Schema generation Failed with error: {error_message}")
            return None
    
    async def _get_defined_schema(self, ingestion_job: DataIngestion):
        try:
            schema = await self._get_prompt_template(ingestion_job.prompt_defined_schema)
            return schema
        except Exception as e:
            error_message = f"Error in fetching defined schema for langfuse: {str(e)}"
            # stack_trace = traceback.format_exc()
            # await self._log_error(ingestion_job, 
            #               error_message, 
            #               "schema_generation", 
            #               error_type="generation", 
            #               is_fatal=True, 
            #               stack_trace=stack_trace)
            
            # # Update schema metadata to reflect failure
            # metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)
            # metadata_state.schema_metadata["error"] = error_message
            # metadata_state.update_pipeline_stage('schema_generation', 'failed')
            # ingestion_job.status_metadata = metadata_state.to_dict()
            # await self._async_save_model(ingestion_job)
            
            # logger.add(f"Schema generation Failed with error: {error_message}")
            return None
    
    async def _create_new_schema(self, ingestion_job: DataIngestion):
        logger.add("Creating new schema")
        chunk_path, chunk_id = await self._chunk_to_process(ingestion_job)
        if chunk_path:
            logger.add(f"Found chunk for schema creation: {chunk_path}")

            chunk_str = await self._format_chunk_for_prompt(chunk_path)
            llm_info = get_active_prompt_from_langfuse(ingestion_job.company_id, self.NEW_SCHEMA_PROMPT_NAME)
            logger.add("Retrieved LLM info from Langfuse")

            prompt_template = await self._get_prompt_template(ingestion_job.prompt_name)
            formatted_prompt = self._custom_template_format(prompt_template, chunk_str=chunk_str)
            final_prompt = PromptTemplate.from_template(formatted_prompt)

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "{system_prompt}"),
                    ("human", "create appropriate schema"),
                ]
            ).partial(system_prompt=final_prompt)

            from chat.clients.workflows.workflow_node import WorkflowLlmNode
            workflow_node = WorkflowLlmNode(name="schema_generation",tools={},prompt_name="schema_generation", include_in_final_response=False)
            chat = workflow_node.get_llm_class(llm_info["llm"])
            state = {}
            script = ""
            try:
                logger.add("Starting AI call for schema generation")
                result = await chat.process_request(state, prompt, llm_info, {}, ingestion_job.company.name, session_id="schema-generation")
                script = result.content
                logger.add(f"Received schema from LLM")
                return True
            except Exception as e:
                logger.add(f"Error in LLM call: {e}")
                return False

        return False
    
    async def _get_neo4j_schema(self, driver):
        logger.add("Fetching Neo4j schema")
        schema_info = {
            'node_labels': {},
            'relationship_types': [],
            'constraints': [],
            'indexes': []
        }
        
        try:
            async with driver.session() as session:
                logger.add("Fetching node labels and properties")
                # Get node labels using MATCH
                result = await session.run("""
                    CALL db.labels() YIELD label
                    RETURN label
                """)
                
                records = await result.records()
                for record in records:
                    label = record["label"]
                    # For each label, get its properties
                    prop_result = await session.run(f"""
                        MATCH (n:{label}) 
                        WHERE n IS NOT NULL
                        RETURN keys(n) AS properties
                        LIMIT 1
                    """)
                    
                    properties = []
                    prop_records = await prop_result.records()
                    for prop_record in prop_records:
                        properties = prop_record["properties"]
                    
                    schema_info['node_labels'][label] = properties
                
                logger.add("Fetching relationship types")
                # Get relationship types
                result = await session.run("""
                    CALL db.relationshipTypes() YIELD relationshipType
                    RETURN relationshipType
                """)
                
                records = await result.records()
                for record in records:
                    schema_info['relationship_types'].append(record["relationshipType"])
                
                logger.add("Fetching constraints")
                # Get constraints
                try:
                    result = await session.run("""
                        SHOW CONSTRAINTS
                    """)
                    
                    records = await result.records()
                    for record in records:
                        constraint_desc = f"Constraint on {record['labelsOrTypes'][0]}.{record['properties'][0]}"
                        schema_info['constraints'].append(constraint_desc)
                except Exception as e:
                    logger.add(f"Error fetching constraints: {e}")
                    # Try alternative method for older Neo4j versions
                    try:
                        result = await session.run("""
                            CALL db.constraints()
                        """)
                        
                        records = await result.records()
                        for record in records:
                            schema_info['constraints'].append(record["description"])
                    except Exception as e2:
                        logger.add(f"Error fetching constraints using alternative method: {e2}")
                
                logger.add("Fetching indexes")
                # Get indexes
                try:
                    result = await session.run("""
                        SHOW INDEXES
                    """)
                    records = await result.records()
                    for record in records:
                        if 'labelsOrTypes' in record and 'properties' in record and len(record['labelsOrTypes']) > 0 and len(record['properties']) > 0:
                            index_desc = f"Index on {record['labelsOrTypes'][0]}({record['properties'][0]})"
                            schema_info['indexes'].append(index_desc)
                except Exception as e:
                    logger.add(f"Error fetching indexes: {e}")
                    # Try alternative method for older Neo4j versions
                    try:
                        result = await session.run("""
                            CALL db.indexes()
                        """)
                        
                        records = await result.records()
                        for record in records:
                            schema_info['indexes'].append(record["description"])
                    except Exception as e2:
                        logger.add(f"Error fetching indexes using alternative method: {e2}")
        
        except Exception as e:
            logger.add(f"Error fetching Neo4j schema: {e}")
        
        is_empty = (
            len(schema_info['node_labels']) == 0 and
            len(schema_info['relationship_types']) == 0 and
            len(schema_info['constraints']) == 0 and
            len(schema_info['indexes']) == 0
        )
        
        if is_empty:
            logger.add("No schema found in neo4j")
            return False
        
        logger.add(f"Schema info retrieved successfully")
        return schema_info
    
    async def _update_completion_from_partitions(self, ingestion_job: DataIngestion):
        """Update the completion percentage of the ingestion job based on partition status"""
        try:
            # Run partition count query in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            total_partitions = await loop.run_in_executor(
                None, 
                lambda: ingestion_job.partitions.count()
            )
            
            if total_partitions == 0:
                logger.add("No partitions found, skipping completion update")
                return
                
            # Count partitions by status
            done_count = await loop.run_in_executor(
                None,
                lambda: ingestion_job.partitions.filter(status=DataIngestionPartition.STATUS_DONE).count()
            )
            
            error_count = await loop.run_in_executor(
                None,
                lambda: ingestion_job.partitions.filter(status=DataIngestionPartition.STATUS_ERROR).count()
            )
            
            # Calculate completion percentage
            processed_count = done_count + error_count
            completion_percentage = int((processed_count / total_partitions) * 100)
            
            # Determine overall status
            if processed_count == total_partitions:
                if error_count == 0:
                    new_status = ingestion_job.STATUS_DONE
                elif done_count == 0:
                    new_status = ingestion_job.STATUS_ERROR
                else:
                    new_status = ingestion_job.STATUS_DONE  # Partial success
            elif processed_count > 0:
                new_status = ingestion_job.STATUS_PROCESSING
            else:
                new_status = ingestion_job.status
                
            # Update job if status or percentage has changed
            if new_status != ingestion_job.status or completion_percentage != ingestion_job.completion_percentage:
                # Update the execution end time if we're transitioning to a final state
                if new_status in [ingestion_job.STATUS_DONE, ingestion_job.STATUS_ERROR] and not ingestion_job.execution_end_at:
                    ingestion_job.execution_end_at = timezone.now()
                    
                ingestion_job.status = new_status
                ingestion_job.completion_percentage = completion_percentage
                
                await self._async_save_model(ingestion_job)
                logger.add(f"Updated job status to {new_status} with completion {completion_percentage}%")
                
        except Exception as e:
            logger.add(f"Error updating completion percentage: {str(e)}")
            logger.add(traceback.format_exc())
    
    async def _format_chunk_for_prompt(self, chunk_path):
        """Read and format chunk file asynchronously"""
        base_dir = "media"
        full_path = os.path.join(os.getcwd(), base_dir, chunk_path)

        file_extension = chunk_path.split('.')[-1].lower()
        try:
            # Use aiofiles for non-blocking file reading
            async with aiofiles.open(full_path, 'r', encoding='utf-8') as file:
                content = await file.read()
                
                if file_extension == 'json':
                    data = json.loads(content)
                    return json.dumps(data, indent=2)
                
                elif file_extension == 'csv':
                    # Process CSV in memory
                    output = io.StringIO()
                    reader = csv.reader(io.StringIO(content))
                    writer = csv.writer(output)
                    for row in reader:
                        writer.writerow(row)
                    return output.getvalue()
                
                else:  # Assume it's a plain text file
                    return content
        
        except Exception as e:
            error_msg = f"Error reading file {chunk_path}: {str(e)}"
            logger.add(error_msg)
            return error_msg
    
    def _custom_template_format(self, template_string, **kwargs):
        """
        Format a template string by replacing only variables in double curly braces {{variable}}
        with their corresponding values.
        """
        def replacer(match):
            # Extract variable name from {{variable}}
            var_name = match.group(1).strip()
            # Return the value if it exists in kwargs, otherwise return the original match
            return str(kwargs.get(var_name, match.group(0)))
        
        # Find all occurrences of {{variable}} and replace them
        pattern = r'{{([^{}]+)}}'
        return re.sub(pattern, replacer, template_string)
    
    async def _get_prompt_template(self, prompt_name) -> str:
        """Fetch and validate prompt template from Langfuse"""
        try:
            logger.add(f"Fetching prompt template: {prompt_name}")
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            prompt_config = await loop.run_in_executor(
                None,
                lambda: self.langfuse_service.get_prompt(prompt_name)
            )
            
            if not prompt_config:
                raise ValueError(f"Prompt '{prompt_name}' not found in Langfuse")
                
            if isinstance(prompt_config, dict):
                prompt_template = prompt_config.get('prompt', '')
            else:
                prompt_template = getattr(prompt_config, 'prompt', '')
                
            if not prompt_template:
                raise ValueError(f"No prompt template found for '{prompt_name}' in Langfuse")
                
            logger.add(f"Successfully fetched prompt template from Langfuse")
            return prompt_template
            
        except Exception as e:
            logger.add(f"Failed to fetch prompt from Langfuse: {str(e)}")
            raise ValueError(f"Failed to fetch prompt from Langfuse: {str(e)}")
    
    async def _setup_neo4j_connection(self):
        """Set up an asynchronous Neo4j connection"""
        # Fetch credentials using thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        credentials = await loop.run_in_executor(
            None,
            lambda: CompanySetting.without_company_objects.get(
                key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS, 
                company=self.company
            )
        )
        
        credentials_dict = {k: v for d in credentials.value for k, v in d.items()}

        neo4j_username = credentials_dict.get("neo4j_username")
        neo4j_password = credentials_dict.get("neo4j_password")
        neo4j_url = credentials_dict.get("neo4j_url")
        
        try:
            driver = AsyncGraphDatabase.driver(
                neo4j_url, 
                auth=(neo4j_username, neo4j_password),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=60,
                connection_timeout=30
            )
            
            # Test connection
            await driver.verify_connectivity()
            logger.add("Neo4j connection successful")
            return driver
            
        except Exception as e:
            logger.add(f"Neo4j connection failed: {e}")
            stack_trace = traceback.format_exc()
            logger.add(stack_trace)
            
            # If we have an active ingestion job, log the connection error
            if hasattr(self, 'current_ingestion_job') and self.current_ingestion_job:
                await self._log_destination_error(
                    self.current_ingestion_job,
                    f"Neo4j connection failed: {str(e)}",
                    error_category="connection",
                    is_connection_error=True,
                    stack_trace=stack_trace
                )
            
            raise
    
    @async_timer
    async def _process_with_prompt(self, ingestion_job: DataIngestion):
        """Process chunks with prompt-based execution using async parallelism"""
        try:
            # Get pending chunks to process
            pending_partitions = await self._get_pending_partitions(ingestion_job)
            
            if not pending_partitions:
                logger.add("No pending partitions found")
                return True
                
            # Process chunks in parallel with limited concurrency
            logger.add(f"Processing {len(pending_partitions)} chunks with max concurrency of {self.max_concurrent_tasks}")
            
            # Create tasks for chunk processing
            tasks = []
            for partition in pending_partitions:
                task = self._process_single_chunk(ingestion_job, partition)
                tasks.append(task)
            
            # Process chunks with semaphore for concurrency control
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            success_count = sum(1 for r in results if r is True)
            error_count = sum(1 for r in results if r is False or isinstance(r, Exception))
            
            logger.add(f"Chunk processing complete: {success_count} successful, {error_count} failed")
            
            # Update completion status
            await self.check_job_completion(ingestion_job)
            
            # Return success if at least one chunk was processed successfully
            return success_count > 0
            
        except Exception as e:
            error_msg = f"Error in prompt processing: {str(e)}"
            stack_trace = traceback.format_exc()
            logger.add(error_msg)
            logger.add(stack_trace)
            
            # Update completion percentage
            await self._update_completion_from_partitions(ingestion_job)
            return False
    
    async def check_job_completion(self, ingestion_job: DataIngestion):
        """
        Check if all partitions have been processed and update job status accordingly
        """
        try:
            # Update completion percentage based on partitions
            await self._update_completion_from_partitions(ingestion_job)
            
            # Check if all partitions are processed
            total_partitions = ingestion_job.partitions.count()
            
            if total_partitions == 0:
                return
                
            done_partitions = ingestion_job.partitions.filter(status=DataIngestionPartition.STATUS_DONE).count()
            error_partitions = ingestion_job.partitions.filter(status=DataIngestionPartition.STATUS_ERROR).count()
            processed_partitions = done_partitions + error_partitions
            
            if processed_partitions == total_partitions:
                # All partitions processed, update final status if not already done
                if ingestion_job.status not in [ingestion_job.STATUS_DONE, ingestion_job.STATUS_ERROR]:
                    # Determine final status based on partition results
                    if error_partitions == 0:
                        ingestion_job.status = ingestion_job.STATUS_DONE
                    elif done_partitions == 0:
                        ingestion_job.status = ingestion_job.STATUS_ERROR
                    else:
                        ingestion_job.status = ingestion_job.STATUS_DONE  # Partial success
                        
                    # Set execution end time if not already set
                    if not ingestion_job.execution_end_at:
                        ingestion_job.execution_end_at = timezone.now()
                        
                    ingestion_job.save()
                    print(f"Updated job final status to {ingestion_job.status}")                 
        except Exception as e:
            print(f"Error checking job completion: {str(e)}")
            import traceback
            traceback.print_exc()

    async def _get_pending_partitions(self, ingestion_job: DataIngestion):
        """Get a batch of pending partitions to process"""
        loop = asyncio.get_event_loop()
        pending_partitions = await loop.run_in_executor(
            None,
            lambda: list(ingestion_job.partitions.filter(
                status=DataIngestionPartition.STATUS_PENDING
            ).order_by('created_at'))
        )
        return pending_partitions
    
    async def _process_single_chunk(self, ingestion_job: DataIngestion, partition: DataIngestionPartition):
        """Process a single chunk with concurrency control"""
        # Use semaphore to limit concurrent processing
        async with self.semaphore:
            start_time = time.time()
            chunk_id = partition.id
            chunk_path = partition.input_file_path
            
            try:
                logger.add(f"Processing chunk {chunk_id}")
                
                # Skip if schema is not available
                if not ingestion_job.status_metadata['schema']:
                    logger.add(f"No schema available, skipping chunk {chunk_id}")
                    return False
                
                # Update partition status to processing
                await self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_PROCESSING)
                
                # Format chunk for processing
                chunk_str = await self._format_chunk_for_prompt(chunk_path)
                
                # Get LLM info and prompt template
                llm_info = get_active_prompt_from_langfuse(ingestion_job.company_id, ingestion_job.prompt_name)
                prompt_template = await self._get_prompt_template(ingestion_job.prompt_name)
                
                # Format prompt with schema and chunk data
                formatted_prompt = self._custom_template_format(
                    prompt_template, 
                    schema_context=ingestion_job.status_metadata['schema'], 
                    chunk_str=chunk_str
                )
                final_prompt = PromptTemplate.from_template(formatted_prompt)

                # Prepare conversation prompt
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "{system_prompt}"),
                    ("human", "start processing the chunk"),
                ]).partial(system_prompt=final_prompt)

                # Initialize LLM client
                from chat.clients.workflows.workflow_node import WorkflowLlmNode
                workflow_node = WorkflowLlmNode(
                    name="data_ingestion",
                    tools={},
                    prompt_name="data_ingestion", 
                    include_in_final_response=False 
                )
                chat = workflow_node.get_llm_class(llm_info["llm"])
                state = {}
                
                # Call LLM to generate Cypher script
                try:
                    logger.add(f"Starting AI call for chunk {chunk_id}")
                    # We need to use chat.process_request directly since it's already awaitable
                    result = await chat.process_request(
                        state, 
                        prompt, 
                        llm_info, 
                        {}, 
                        ingestion_job.company.name, 
                        session_id=f"data-ingestion-{chunk_id}"
                    )
                    script = result.content
                    logger.add(f"Received Cypher script from LLM for chunk {chunk_id}")
                except Exception as e:
                    error_msg = f"Error during LLM processing for chunk {chunk_id}: {str(e)}"
                    logger.add(error_msg)
                    
                    # Log errors and update partition status
                    await self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_ERROR, error_msg)
                    
                    # Update completion percentage
                    await self._update_completion_from_partitions(ingestion_job)
                    return False

                # Execute Cypher script if we got a valid result
                if script:
                    try:
                        # Execute the Cypher script against Neo4j
                        results = await self._execute_cypher_script(script, ingestion_job, chunk_id)
                        
                        # Check for execution failures
                        if results:
                            for i, result in enumerate(results):
                                if not result.get('success', False):
                                    error_msg = f"Cypher execution error: {result.get('error', 'Unknown error')}"
                    except Exception as e:
                        error_msg = f"Failed to execute Cypher script for chunk {chunk_id}: {str(e)}"
                        stack_trace = traceback.format_exc()
                        logger.add(error_msg)
                        logger.add(stack_trace)
                        return False
                else:
                    logger.add(f"No valid Cypher script generated for chunk {chunk_id}")
                    return False
                
                # Update chunk status to completed
                end_time = time.time()
                processing_time_seconds = end_time - start_time
                
                # Update partition status to done
                await self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_DONE)
                
                # Update completion percentage
                await self._update_completion_from_partitions(ingestion_job)
                
                logger.add(f"Chunk {chunk_id} processed in {processing_time_seconds:.2f} seconds")
                return True
                
            except Exception as e:
                # Calculate processing time even for failed chunks
                end_time = time.time()
                processing_time_seconds = end_time - start_time
                
                error_msg = f"Error processing chunk {chunk_id}: {str(e)}"
                stack_trace = traceback.format_exc()
                logger.add(error_msg)
                logger.add(stack_trace)
                
                # Update partition status to error
                await self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_ERROR, error_msg)
                
                logger.add(f"Chunk {chunk_id} failed after {processing_time_seconds:.2f} seconds")
                return False
            
    async def _update_partition_status(self, ingestion_job, partition_id, status, error_message=None):
        """
        Update the status of a partition record associated with a chunk
        
        Args:
            ingestion_job: DataIngestion model instance
            partition_id: The partition ID to update
            status: New status for the partition (pending, processing, done, error)
            error_message: Optional error message for failed partitions
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:

            from django.db.models import Q
            target_partition = await self._async_db_operation(
                lambda: DataIngestionPartition.objects.filter(id=partition_id).first()
            )
            
            # If partition found, update its status
            if target_partition:
                # Calculate processing time if completing or erroring
                if status in [DataIngestionPartition.STATUS_DONE, DataIngestionPartition.STATUS_ERROR]:
                    if target_partition.started_at:
                        processing_time = (timezone.now() - target_partition.started_at).total_seconds()
                        target_partition.processing_time = processing_time
                
                # Set status and timestamps
                target_partition.status = status
                
                if status == DataIngestionPartition.STATUS_PROCESSING:
                    target_partition.started_at = timezone.now()
                elif status == DataIngestionPartition.STATUS_DONE:
                    target_partition.processed_at = timezone.now()
                
                # Set error message if provided
                if error_message:
                    target_partition.error_message = error_message
                
                # Update metadata if needed
                if target_partition.metadata is None:
                    target_partition.metadata = {}
                
                target_partition.metadata.update({
                    'updated_at': timezone.now().isoformat(),
                    'status_history': target_partition.metadata.get('status_history', []) + [
                        {'status': status, 'timestamp': timezone.now().isoformat()}
                    ]
                })
                
                # Use async save method instead of direct save
                await self._async_save_model(target_partition)
                logger.add(f"Updated partition {target_partition.id} status to {status}")
                return True
            else:
                logger.add(f"No partition found with ID {partition_id}")
                return False
                
        except Exception as e:
            logger.add(f"Error updating partition status: {str(e)}")
            import traceback
            logger.add(traceback.format_exc())
            return False