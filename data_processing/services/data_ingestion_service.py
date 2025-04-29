import asyncio
import json
import csv
import io
import os
import traceback
from neo4j import GraphDatabase
from django.utils import timezone
from chat.assistants import get_active_prompt_from_langfuse
from company.models import CompanySetting
from data_processing.file_chunker import FileChunker
from data_processing.states.ingestion_error_state import IngestionErrorState
from data_processing.states.ingestion_metadata_state import IngestionMetadataState
from backend.services.langfuse_service import LangfuseService
from data_processing.models import DataIngestion, DataIngestionPartition
from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
import re
from backend.logger import Logger
# Configure logger
logger = Logger(Logger.INFO_LOG)

class DataIngestionService:
    """
    Service for handling data ingestion into Neo4j graph database.
    Provides methods for processing files, generating Cypher queries,
    and executing them against a Neo4j database.
    """
    
    def __init__(self, ingestion_job: DataIngestion=None):
        """Initialize the DataIngestionService"""
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

        if ingestion_job is not None:
            if (hasattr(ingestion_job, 'status_metadata') and 
                ingestion_job.status_metadata is not None and 
                ingestion_job.status_metadata != "null" and 
                ingestion_job.status_metadata != ""):
                self.metadata_state = IngestionMetadataState.from_dict(ingestion_job.status_metadata)
            else:
                self.metadata_state = IngestionMetadataState()
                
            if (hasattr(ingestion_job, 'processing_error') and 
                ingestion_job.processing_error is not None and 
                ingestion_job.processing_error != "null" and 
                ingestion_job.processing_error != ""):
                
                self.error_state = IngestionErrorState.from_dict(ingestion_job.processing_error)
            else:
                self.error_state = IngestionErrorState()
        else:
            self.metadata_state = IngestionMetadataState()
            self.error_state = IngestionErrorState()
        
        self.company = ingestion_job.company

            
    def _initialize_ingestion_metadata(self, ingestion_job: DataIngestion):
        """Prepare ingestion job metadata."""
        if (ingestion_job.status == DataIngestion.STATUS_PENDING):
            ingestion_job.execution_start_at = timezone.now()
            ingestion_job.status = DataIngestion.STATUS_PROCESSING
            ingestion_job.save()

        if ingestion_job.status_metadata is None:
            self.metadata_state.destination_metadata["type"] = ingestion_job.destination
            ingestion_job.status_metadata = self.metadata_state.to_dict()
            ingestion_job.save()

        if not hasattr(ingestion_job, 'processing_error') or ingestion_job.processing_error is None:
            error_state = self.error_state
            ingestion_job.processing_error = error_state.to_dict()
            ingestion_job.save()
        # else:
        #     # Initialize error state from existing data
        #     if isinstance(ingestion_job.processing_error, dict):
        #         self.error_state = self.error_state.from_dict(ingestion_job.processing_error)
        #     elif isinstance(ingestion_job.processing_error, str):
        #         try:
        #             self.error_state = self.error_state.from_json(ingestion_job.processing_error)
        #         except json.JSONDecodeError:
        #             # If the error state is not valid JSON, initialize a new one
        #             self.error_state = IngestionErrorState()
        #             ingestion_job.processing_error = self.error_state.to_dict()
        #             ingestion_job.save()
        
        self.langfuse_service = LangfuseService(ingestion_job.company_id)

    def reset_job_partitions(self, ingestion_job: DataIngestion):
        """
        Reset all partitions to pending status for a job
        
        Args:
            ingestion_job: DataIngestion model instance
            
        Returns:
            dict: Summary of reset operation
        """
        try:
            # Check if job is currently processing
            if ingestion_job.status == DataIngestion.STATUS_PROCESSING:
                raise ValueError("Cannot reset job while it is being processed")
                
            # Reset all partitions to pending
            partitions = ingestion_job.partitions.all()
            total_partitions = partitions.count()
            
            partitions.update(
                status=DataIngestionPartition.STATUS_PENDING,
                processed_at=None,
                error_message=None,
                metadata={
                    "reset_at": timezone.now().isoformat(),
                    "previous_status": str(ingestion_job.status),
                    "request_id": str(ingestion_job.id)
                }
            )
            
            # Reset job status and metadata
            ingestion_job.status = DataIngestion.STATUS_PENDING
            ingestion_job.completion_percentage = 0
            ingestion_job.execution_start_at = None
            ingestion_job.execution_end_at = None
            
            ingestion_job.save()
            
            return {
                "total_partitions": total_partitions,
                "status": "reset_complete"
            }
        
        except ValueError as e:
            raise e
        except Exception as e:
            print(f"Error resetting job partitions: {str(e)}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Failed to reset partitions: {str(e)}")
    
    def _process_schema_generation(self, ingestion_job: DataIngestion):
        schema = {}
        stage = 'schema_generation'
        try:
            if ingestion_job.schema_type == "defined":
                schema = self._get_defined_schema(ingestion_job)
                if not schema:
                    self._update_metadata(ingestion_job, stage, 'failed')
                    print("\n Schema not provided in selected prompt\n")
            else:
                driver = self._setup_neo4j_connection()
                schema = self._get_neo4j_schema(driver)

                if not schema:
                    schema = self._create_new_schema(ingestion_job)
                    if not schema:
                        self._update_metadata(ingestion_job, stage, 'failed')
                        self._log_error(ingestion_job, 
                                        "Failed to create new schema using LLM", 
                                        stage, 
                                        error_type="generation", 
                                        is_fatal=True)
                        print("\n Schema generation Failed \n")
                        return
            
            # Update schema in metadata state
            metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)

            # refactor
            # no need to save schema everytime
            metadata_state.update_schema(schema, "completed")
            ingestion_job.status_metadata = metadata_state.to_dict()
            ingestion_job.save()
            
            self._update_metadata(ingestion_job, stage, 'completed')
            return schema
        
        except Exception as e:
            error_message = f"Error in schema generation: {str(e)}"
            stack_trace = traceback.format_exc()
            self._log_error(ingestion_job, 
                          error_message, 
                          "schema_generation", 
                          error_type="generation", 
                          is_fatal=True, 
                          stack_trace=stack_trace)
            self._update_metadata(ingestion_job, 'schema_generation', 'failed')
            print(f"\n Schema generation Failed with error: {error_message} \n")
            return None

    def _get_defined_schema(self, ingestion_job: DataIngestion):
        try:
            schema = self._get_prompt_template(ingestion_job.prompt_defined_schema)
        except Exception as e:
            error_message = f"Error in fetching defined schema for langfuse: {str(e)}"
            stack_trace = traceback.format_exc()
            self._log_error(ingestion_job, 
                          error_message, 
                          "schema_generation", 
                          error_type="generation", 
                          is_fatal=True, 
                          stack_trace=stack_trace)
            
            # Update schema metadata to reflect failure
            metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)
            metadata_state.schema_metadata["error"] = error_message
            metadata_state.update_pipeline_stage('schema_generation', 'failed')
            ingestion_job.status_metadata = metadata_state.to_dict()
            ingestion_job.save()
            
            print(f"\n Schema generation Failed with error: {error_message} \n")
            return None
        return schema

    def _create_new_schema(self, ingestion_job: DataIngestion):
        print(f"\n _create_new_schema \n")
        chunk_path, chunk_id = self._chunk_to_process(ingestion_job)
        if chunk_path:
            print(f"\n _create_new_schema found chunk\n")

            chunk_str = self._format_chunk_for_prompt(chunk_path)
            llm_info = get_active_prompt_from_langfuse(ingestion_job.company_id, self.NEW_SCHEMA_PROMPT_NAME)
            print(f"\n _create_new_schema found llm_info\n")

            prompt_template = self._get_prompt_template(ingestion_job.prompt_name)
            formatted_prompt = self._custom_template_format(prompt_template, chunk_str=chunk_str)
            final_prompt = PromptTemplate.from_template(formatted_prompt)

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "{system_prompt}"),
                    ("human", "create appropriate schema"),
                ]
            ).partial(system_prompt=final_prompt)

            from chat.clients.workflows.workflow_node import WorkflowLlmNode
            workflow_node = WorkflowLlmNode(name="schema_generation",tools={},prompt_name="schema_generation", include_in_final_response=False )
            chat = workflow_node.get_llm_class(llm_info["llm"])
            state = {}
            script = ""
            try:
                print("\n starting ai call\n")
                result = asyncio.run(chat.process_request(state, prompt, llm_info, {}, ingestion_job.company.name, session_id="schema-generation"))
                script = result.content
                print(f"\n result from llm : {script} \n")
            except Exception as e:
                print(f"\n LLLLLLL : {e}\n")
                return False

            return True

    def _get_neo4j_schema(self, driver):
        print("\n==== FETCHING NEO4J SCHEMA ====\n")
        schema_info = {
            'node_labels': {},
            'relationship_types': [],
            'constraints': [],
            'indexes': []
        }
        try:
            with driver.session() as session:
                print("\n-- Fetching node labels and properties --\n")
                # Get node labels using MATCH
                result = session.run("""
                    CALL db.labels() YIELD label
                    RETURN label
                """)
                
                for record in result:
                    label = record["label"]
                    # For each label, get its properties
                    prop_result = session.run(f"""
                        MATCH (n:{label}) 
                        WHERE n IS NOT NULL
                        RETURN keys(n) AS properties
                        LIMIT 1
                    """)
                    
                    properties = []
                    for prop_record in prop_result:
                        properties = prop_record["properties"]
                    
                    schema_info['node_labels'][label] = properties
                
                print("\n-- Fetching relationship types --\n")
                # Get relationship types
                result = session.run("""
                    CALL db.relationshipTypes() YIELD relationshipType
                    RETURN relationshipType
                """)
                
                for record in result:
                    schema_info['relationship_types'].append(record["relationshipType"])
                
                print("\n-- Fetching constraints --\n")
                # Get constraints
                try:
                    result = session.run("""
                        SHOW CONSTRAINTS
                    """)
                    
                    for record in result:
                        constraint_desc = f"Constraint on {record['labelsOrTypes'][0]}.{record['properties'][0]}"
                        schema_info['constraints'].append(constraint_desc)
                except Exception as e:
                    print(f"Error fetching constraints: {e}")
                    # Try alternative method for older Neo4j versions
                    try:
                        result = session.run("""
                            CALL db.constraints()
                        """)
                        
                        for record in result:
                            schema_info['constraints'].append(record["description"])
                    except Exception as e2:
                        print(f"Error fetching constraints using alternative method: {e2}")
                
                print("\n-- Fetching indexes --\n")
                # Get indexes
                try:
                    result = session.run("""
                        SHOW INDEXES
                    """)
                    for record in result:
                        if 'labelsOrTypes' in record and 'properties' in record and len(record['labelsOrTypes']) > 0 and len(record['properties']) > 0:
                            index_desc = f"Index on {record['labelsOrTypes'][0]}({record['properties'][0]})"
                            schema_info['indexes'].append(index_desc)
                except Exception as e:
                    print(f"Error fetching indexes: {e}")
                    # Try alternative method for older Neo4j versions
                    try:
                        result = session.run("""
                            CALL db.indexes()
                        """)
                        
                        for record in result:
                            schema_info['indexes'].append(record["description"])
                    except Exception as e2:
                        print(f"Error fetching indexes using alternative method: {e2}")
        
        except Exception as e:
            print(f"Error fetching Neo4j schema: {e}")
        
        is_empty = (
            len(schema_info['node_labels']) == 0 and
            len(schema_info['relationship_types']) == 0 and
            len(schema_info['constraints']) == 0 and
            len(schema_info['indexes']) == 0
        )
        
        if is_empty:
            print("\n-- No schema found in neo4j --\n")
            return False
        
        print(f"\n-- Schema info: {json.dumps(schema_info, indent=2)} --\n")
        return schema_info

    def process_ingestion_job(self, ingestion_job: DataIngestion) -> bool:
        """Process a data ingestion job
        
        Args:
            ingestion_job: The DataIngestion model instance to process

        Returns:
            bool: True if successful, False otherwise
        """
        # Store reference to current ingestion job for error handling
        self.current_ingestion_job = ingestion_job
        
        try:
            self._initialize_ingestion_metadata(ingestion_job)
            # Update completion percentage based on existing partitions
            self._update_completion_from_partitions(ingestion_job)
            schema = self._process_schema_generation(ingestion_job)

            if not schema:
                # add llm call to generate schema first
                pass

            # Validate file extension
            file_extension = ingestion_job.file.name.split('.')[-1].lower()
            print(f"\n file_extension : {file_extension} \n")

            chunking_status = ingestion_job.chunking_status
            print(f"\n current chunking status : {chunking_status} \n")

            if chunking_status == DataIngestion.CHUNKING_STATUS_PENDING:
                if file_extension not in self.supported_file_types:
                    error_msg = f"Unsupported file type: {file_extension}"
                    return False
                
                ingestion_job.chunking_status = DataIngestion.CHUNKING_STATUS_PROCESSING
                ingestion_job.save()
                
                # Process file chunking
                logger.add("Starting file chunking process")
                try:
                    chunker = FileChunker(ingestion_job)
                    if not chunker.process_file():
                        error_msg = "File chunking failed"
                        self._handle_error(ingestion_job, error_msg, 'chunking')
                        self._log_error(ingestion_job, 
                                    error_msg, 
                                    "chunking", 
                                    error_type="processing", 
                                    is_fatal=True)
                        return False
                except Exception as chunk_error:
                    error_msg = f"File chunking failed with error: {str(chunk_error)}"
                    stack_trace = traceback.format_exc()
                    return False

                self._update_metadata(ingestion_job, 'chunking', 'completed')
                print("File chunking completed successfully")

                logger.add("File chunking completed successfully")

                self._update_completion_from_partitions(ingestion_job)

            else:
                logger.add("Chunking already complete, moving forward")
                    
            # Process based on execution type
            if ingestion_job.execution_type == ingestion_job.EXECUTION_TYPE_WORKFLOW:
                # return self._process_with_workflow(ingestion_job)
                # will add later
                pass

            elif ingestion_job.execution_type == ingestion_job.EXECUTION_TYPE_PROMPT:
                return self._process_with_prompt(ingestion_job)
            else:
                error_msg = f"Unknown execution type: {ingestion_job.execution_type}"
                self._handle_error(ingestion_job, error_msg, 'initialization', error_type="validation", is_fatal=True)
                return False

        except Exception as e:
            # logger.error(f"An unexpected error occurred: {str(e)}")
            error_msg = f"An unexpected error occurred: {str(e)}"
            stack_trace = traceback.format_exc()
            print(f"\n{error_msg}\n")
            traceback.print_exc()
            self._handle_error(ingestion_job, error_msg, "processing", error_type="error", is_fatal=True, stack_trace=stack_trace)
            return False
    


    def _update_completion_from_partitions(self, ingestion_job: DataIngestion):
        """
        Update the completion percentage of the ingestion job based on partition status
        """
        try:
            # Get partition counts
            total_partitions = ingestion_job.partitions.count()
            if total_partitions == 0:
                print("No partitions found, skipping completion update")
                return
                
            # Count partitions by status
            done_count = ingestion_job.partitions.filter(status=DataIngestionPartition.STATUS_DONE).count()
            error_count = ingestion_job.partitions.filter(status=DataIngestionPartition.STATUS_ERROR).count()
            
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
                
                ingestion_job.save()
                print(f"Updated job status to {new_status} with completion {completion_percentage}%")
                
        except Exception as e:
            print(f"Error updating completion percentage: {str(e)}")
            import traceback
            traceback.print_exc()

    def check_job_completion(self, ingestion_job: DataIngestion):
        """
        Check if all partitions have been processed and update job status accordingly
        """
        try:
            # Update completion percentage based on partitions
            self._update_completion_from_partitions(ingestion_job)
            
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
                    
                    # Update metadata final stage status
                    self._update_metadata(ingestion_job, 'knowledge_graph_creation', 'completed')
                    
        except Exception as e:
            print(f"Error checking job completion: {str(e)}")
            import traceback
            traceback.print_exc()


    def _format_chunk_for_prompt(self, chunk_path):
        # this should be saved by chunker
        base_dir = "media"
        full_path = os.path.join(os.getcwd(), base_dir, chunk_path)

        file_extension = chunk_path.split('.')[-1].lower()
        try:
            with open(full_path, 'r', encoding='utf-8') as file:
                if file_extension == 'json':
                    data = json.load(file)
                    return json.dumps(data, indent=2)
                
                elif file_extension == 'csv':
                    output = io.StringIO()
                    reader = csv.reader(file)
                    writer = csv.writer(output)
                    writer.writerows(reader)
                    return output.getvalue()
                
                else:  # Assume it's a plain text file
                    return file.read()
        
        except Exception as e:
            error_msg = f"Error reading file {chunk_path}: {str(e)}"
            print(error_msg)
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

    def _process_with_prompt(self, ingestion_job: DataIngestion):
        chunk_id = None
        start_time = timezone.now()
        try:
            chunk_path, chunk_id = self._chunk_to_process(ingestion_job)
            print(f"\n chunk_path : {chunk_path}\n")
            print(f"\n chunk_id : {chunk_id}\n")
            
            if chunk_path and ingestion_job.status_metadata['schema']:
                self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_PROCESSING)
                
                chunk_str = self._format_chunk_for_prompt(chunk_path)

                llm_info = get_active_prompt_from_langfuse(ingestion_job.company_id, ingestion_job.prompt_name)
                prompt_template = self._get_prompt_template(ingestion_job.prompt_name)
                formatted_prompt = self._custom_template_format(prompt_template, schema_context=ingestion_job.status_metadata['schema'], chunk_str=chunk_str)
                final_prompt = PromptTemplate.from_template(formatted_prompt)

                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", "{system_prompt}"),
                        ("human", "start processing the chunk"),
                    ]
                ).partial(system_prompt=final_prompt)

                from chat.clients.workflows.workflow_node import WorkflowLlmNode
                workflow_node = WorkflowLlmNode(name="data_ingestion",tools={},prompt_name="data_ingestion", include_in_final_response=False )
                chat = workflow_node.get_llm_class(llm_info["llm"])
                state = {}
                script = ""
                try:
                    print("\n starting ai call\n")
                    result = asyncio.run(chat.process_request(state, prompt, llm_info, {}, ingestion_job.company.name, session_id="data-ingestion"))
                    script = result.content
                    print(f"\n result from llm : {script} \n")
                except Exception as e:
                    print(f"\n LLLLLLLfklajdsfl : {e}\n")
                    error_msg = f"Error during LLM processing: {str(e)}"
                    
                    # Log errors and update partition status
                    self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_ERROR, error_msg)
                    context = {"chunk_id": chunk_id}
                    self._log_error(ingestion_job, error_msg, "processing", error_type="llm_error", is_fatal=False, context=context)
                    self._log_partition_error(ingestion_job, chunk_id, error_msg, "llm_processing")
                    
                    # Update completion percentage based on partition status
                    self._update_completion_from_partitions(ingestion_job)
                    
                    return False

                if script:
                    # cleaned_script = self._clean_script(script)
                    # print(f"\n cleaned cleaned_script : {cleaned_script} \n")
                    try:
                        results = self._execute_cypher_script(script, ingestion_job, chunk_id)
                        # Check for any execution failures
                        if results:
                            for i, result in enumerate(results):
                                if not result.get('success', False):
                                    error_msg = f"Cypher execution error: {result.get('error', 'Unknown error')}"
                                    self._log_partition_error(
                                        ingestion_job, 
                                        chunk_id, 
                                        error_msg, 
                                        "cypher_execution",
                                        metadata={
                                            "statement": result.get('statement', ''),
                                            "statement_index": i,
                                            "suggestion": result.get('suggestion')
                                        }
                                    )
                    except Exception as e:
                        error_msg = f"Failed to execute Cypher script: {str(e)}"
                        stack_trace = traceback.format_exc()
                        self._log_partition_error(
                            ingestion_job, 
                            chunk_id, 
                            error_msg, 
                            "cypher_execution",
                            is_fatal=True,
                            stack_trace=stack_trace
                        )
                        # Log to destination errors as well
                        self._log_destination_error(ingestion_job, error_msg, chunk_id)
                        return False
            else:
                print("\nNO pending chunk found\n")
            
            # Update chunk status to completed
            if chunk_id:
                # Calculate processing time directly
                end_time = timezone.now()
                processing_time_seconds = (end_time - start_time).total_seconds()
                
                # Update partition status to done
                self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_DONE)
                
                # Update completion percentage based on partition status
                self._update_completion_from_partitions(ingestion_job)
                
                # Display the processing time
                print(f"\nChunk {chunk_id} processed in {processing_time_seconds:.2f} seconds\n")
                
            return True
            
        except Exception as e:
            # Calculate processing time even for failed chunks
            end_time = timezone.now()
            processing_time_seconds = (end_time - start_time).total_seconds()
            
            error_msg = f"Error in prompt processing: {str(e)}"
            stack_trace = traceback.format_exc()
            
            if chunk_id:
                # Update partition status to error
                self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_ERROR, error_msg)
                self._log_partition_error(ingestion_job, chunk_id, error_msg, "processing", is_fatal=True, stack_trace=stack_trace)
                # Display the processing time for the failed chunk
                print(f"\nChunk {chunk_id} failed after {processing_time_seconds:.2f} seconds\n")
            
            # Log general error
            self._log_error(ingestion_job, 
                          error_msg, 
                          "processing", 
                          error_type="error", 
                          is_fatal=False, 
                          stack_trace=stack_trace)
            
            # Update completion percentage based on partition status
            self._update_completion_from_partitions(ingestion_job)
                
            print(f"\n Error during prompt processing: {error_msg}\n")
            traceback.print_exc()
            return False
    
    def _clean_script(self, script):
        script = script.strip()
        if script.startswith("```cypher"):
            script = script.replace("```cypher", "", 1)
            print("-- Removed ```cypher prefix --")
        if script.startswith("```"):
            script = script.replace("```", "", 1)
            print("-- Removed ``` prefix --")
        if script.endswith("```"):
            script = script[:-3]
            print("-- Removed ``` suffix --")
        
        script = script.strip()
        return script
    
    def _parse_cypher_statements(self, script):
        """
        Parse Cypher script into individual statements by splitting on semicolons.
        Handles semicolons inside string literals properly and removes comments.
        
        Args:
            cypher_script: Original Cypher script
            
        Returns:
            list: List of individual Cypher statements
        """
        # First, remove comments
        lines = []
        for line in script.split('\n'):
            if '//' in line:
                comment_pos = line.find('//')
                # Check if the // is inside a string literal
                in_string = False
                for i in range(comment_pos):
                    if line[i] == '"' or line[i] == "'":
                        in_string = not in_string
                
                if not in_string:
                    line = line[:comment_pos]
            
            if line.strip():
                line  = self._clean_script(line)
                lines.append(line)
        
        # Join all non-empty lines
        script = '\n'.join(lines)
        
        # Handle semicolons inside string literals
        in_string = False
        string_delimiter = None
        escape_next = False
        safe_script = ""
        
        for char in script:
            if escape_next:
                safe_script += char
                escape_next = False
                continue
                
            if char == '\\':
                safe_script += char
                escape_next = True
                continue
                
            if char in ['"', "'"]:
                if not in_string:
                    in_string = True
                    string_delimiter = char
                elif char == string_delimiter:
                    in_string = False
                    
            if char == ';' and in_string:
                # Replace semicolons in strings with a placeholder
                safe_script += "###SEMICOLON###"
            else:
                safe_script += char
        
        # Split by semicolons
        raw_statements = []
        for stmt in safe_script.split(';'):
            stmt = stmt.strip()
            if stmt:
                # Restore semicolons in string literals
                stmt = stmt.replace("###SEMICOLON###", ";")
                raw_statements.append(stmt)
        
        # Add semicolons back to the statements
        statements = [stmt + ";" for stmt in raw_statements]
        
        return statements

    def _fix_statement_syntax(self, statement):
        """
        Fix syntax issues in a single Cypher statement
        
        Args:
            statement: Original Cypher statement
            
        Returns:
            str: Fixed Cypher statement
        """
        import re
        
        # Remove trailing semicolon if present
        statement = statement.rstrip().rstrip(';')
        
        # Ensure MATCH statements have a RETURN clause
        if re.match(r'^\s*MATCH\b', statement, re.IGNORECASE) and not re.search(r'\bRETURN\b', statement, re.IGNORECASE):
            # Extract node variables from the MATCH statement
            node_vars = re.findall(r'\(\s*(\w+)\s*:', statement)
            
            if node_vars:
                # Add RETURN clause with all node variables
                return_vars = ', '.join(node_vars)
                statement = f"{statement}\nRETURN {return_vars}"
            else:
                # If no node variables found, just return 1
                statement = f"{statement}\nRETURN 1"
        
        # Ensure statement ends with a semicolon
        if not statement.rstrip().endswith(';'):
            statement += ";"
            
        return statement

    def _suggest_fix_for_error(self, error_msg, statement):
        """
        Suggest fixes for common Cypher errors
        
        Args:
            error_msg: Error message from Neo4j
            statement: The Cypher statement that caused the error
            
        Returns:
            str: Suggestion to fix the error, or None if no suggestion
        """
        import re
        
        # Check for "Query cannot conclude with MATCH" error
        if "Query cannot conclude with MATCH" in error_msg:
            # Extract node variables from the MATCH statement
            node_vars = re.findall(r'\(\s*(\w+)\s*:', statement)
            
            if node_vars:
                # Suggest adding a RETURN clause with the node variables
                return_vars = ', '.join(node_vars)
                return f"Add a RETURN clause at the end of the statement: RETURN {return_vars};"
            else:
                # If no node variables found, just return 1
                return "Add a RETURN clause at the end of the statement, e.g., RETURN 1;"
        
        # Check for "expected to find a property name" error
        elif "expected to find a property name" in error_msg:
            return "Check your property syntax in the Cypher statement. Make sure all property names are valid and properly formatted."
        
        # Check for "Invalid input" errors
        elif "Invalid input" in error_msg:
            return "There's a syntax error in your Cypher statement. Check for missing quotes, brackets, or other syntax elements."
        
        # No specific suggestion
        return None

    def _execute_cypher_script(self, cypher_script, ingestion_job: DataIngestion, partition_id=None):
        """Execute a single Cypher script and return the results
        
        Args:
            cypher_script: The Cypher script to execute
            ingestion_job: The DataIngestion model instance
            partition_id: Optional ID of the partition being processed
            
        Returns:
            list: Results of executing each statement
        """
        print(f"\n==== EXECUTING SINGLE CYPHER SCRIPT ====\n")
        print(f"\n-- Cypher script :\n {cypher_script}...\n--\n")
        
        try:
            # Parse the script into individual statements
            statements = self._parse_cypher_statements(cypher_script)
            
            print(f"Found {len(statements)} separate Cypher statements to execute")
            driver = self._setup_neo4j_connection()
            results = []
            
            # Update metadata to reflect knowledge graph creation in progress
            self._update_metadata(ingestion_job, 'knowledge_graph_creation', 'in_progress')
            
            nodes_created = 0
            relationships_created = 0
            
            with driver.session() as session:
                for i, statement in enumerate(statements):
                    statement_index = i+1
                    print(f"\nExecuting statement {statement_index}/{len(statements)}")
                    try:
                        # Apply statement-specific fixes
                        fixed_statement = self._fix_statement_syntax(statement)
                        if fixed_statement != statement:
                            print(f"Fixed statement syntax. Original:\n{statement}\n\nFixed:\n{fixed_statement}")
                            statement = fixed_statement
                            
                        result = session.run(statement)
                        summary = result.consume()
                        
                        # Track nodes and relationships created
                        if hasattr(summary.counters, 'nodes_created'):
                            nodes_created += summary.counters.nodes_created
                        if hasattr(summary.counters, 'relationships_created'):
                            relationships_created += summary.counters.relationships_created
                        
                        results.append({
                            'statement': statement,
                            'counters': summary.counters,
                            'success': True
                        })
                        print(f"Statement {statement_index} executed successfully: {summary.counters}")
                    except Exception as e:
                        error_msg = str(e)
                        print(f"Error executing statement {statement_index}: {error_msg}")
                        
                        # Try to provide helpful feedback for common errors
                        suggestion = self._suggest_fix_for_error(error_msg, statement)
                        if suggestion:
                            print(f"Suggestion to fix error: {suggestion}")
                        
                        print("\n logging error \n")
                        self._log_destination_error(
                            ingestion_job, 
                            error_msg, 
                            partition_id, 
                            operation_type="cypher_execution",
                            query=statement
                        )

                        results.append({
                            'statement': statement,
                            'error': error_msg,
                            'suggestion': suggestion if suggestion else None,
                            'success': False
                        })
                        # Don't break on error, try to execute remaining statements
            
            # Update destination stats with created nodes and relationships
            if nodes_created > 0 or relationships_created > 0:
                self._update_destination_stats(ingestion_job, nodes_created, relationships_created, partition_id)
                
            # Update metadata to reflect knowledge graph creation completion if successful
            if all(result.get('success', False) for result in results):
                self._update_metadata(ingestion_job, 'knowledge_graph_creation', 'completed')
            
            return results
            
        except Exception as e:
            import traceback

            print(f"\n==== ERROR EXECUTING CYPHER: {e} ====\n")
            error_msg = f"Error executing Cypher: {str(e)}"
            stack_trace = traceback.format_exc()
            
            self._log_destination_error(
                ingestion_job, 
                error_msg, 
                None, 
                is_connection_error=False, 
                operation_type="cypher_batch_execution"
            )
            
            traceback.print_exc()
            raise

    def _chunk_to_process(self, ingestion_job: DataIngestion):
        """Get the next partition to process based solely on the DataIngestionPartition model
        
        Args:
            ingestion_job: The DataIngestion model instance
            
        Returns:
            tuple: (input_file_path, partition_id) or (None, None) if no pending partitions
        """
        # Get a few pending partitions to have options in case of contention
        pending_partitions = list(ingestion_job.partitions.filter(
            status=DataIngestionPartition.STATUS_PENDING
        ).order_by('created_at')[:5])
        
        if not pending_partitions:
            print("No pending partitions found")
            return None, None
        
        # Try to claim one partition - loop through our options in case of contention
        for pending_partition in pending_partitions:
            # Check if this partition is still pending (might have changed since query)
            partition_id = pending_partition.id
            current_status = DataIngestionPartition.objects.filter(
                id=partition_id, 
                status=DataIngestionPartition.STATUS_PENDING
            ).update(status=DataIngestionPartition.STATUS_PROCESSING)
            
            # If update count is 0, another process claimed it first
            if current_status == 0:
                print(f"Partition {partition_id} was already claimed by another process")
                continue
            
            # Successfully claimed this partition!
            print(f"Successfully claimed partition {partition_id} for processing")
            
            # Refresh from database to get updated data
            pending_partition.refresh_from_db()
            
            # Update partition metadata and timestamps
            if pending_partition.metadata is None:
                pending_partition.metadata = {}
            
            # Set started_at timestamp
            pending_partition.started_at = timezone.now()
            
            # Add processing timestamp to partition metadata for history tracking
            pending_partition.metadata.update({
                'processing_started_at': timezone.now().isoformat(),
                'status_history': pending_partition.metadata.get('status_history', []) + [
                    {'status': 'processing', 'timestamp': timezone.now().isoformat()}
                ]
            })
            pending_partition.save()
            
            # Extract chunk_id from partition metadata
            if not partition_id:
                # Reset partition to pending since we can't process it
                pending_partition.status = DataIngestionPartition.STATUS_PENDING
                pending_partition.save()
                continue
            
            return pending_partition.input_file_path, partition_id
        
        # If we get here, all attempts to claim a partition failed
        print("Could not claim any pending partition")
        return None, None
    
    def _update_destination_stats(self, ingestion_job: DataIngestion, nodes_created=0, relationships_created=0, partition_id=None):
        """Update destination statistics in the DataIngestionPartition model and job metadata
        
        Args:
            ingestion_job: The DataIngestion model instance
            nodes_created: Number of nodes created in this operation
            relationships_created: Number of relationships created in this operation
            partition_id: Optional ID of the partition being processed
        """
        # Update the specific partition if provided
        if partition_id:
            try:
                partition = DataIngestionPartition.objects.get(id=partition_id)
                
                # Update partition stats
                if partition.metadata is None:
                    partition.metadata = {}
                
                # Initialize or update destination stats in partition metadata
                if 'destination_stats' not in partition.metadata:
                    partition.metadata['destination_stats'] = {
                        'nodes_created': 0,
                        'relationships_created': 0
                    }
                
                # Add to existing stats
                partition.metadata['destination_stats']['nodes_created'] += nodes_created
                partition.metadata['destination_stats']['relationships_created'] += relationships_created
                partition.save()
            except Exception as e:
                print(f"Error updating partition stats: {str(e)}")
        
        # For backward compatibility, also update the job metadata
        if ingestion_job.status_metadata and isinstance(ingestion_job.status_metadata, dict):
            metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)
            metadata_state.update_destination_stats(nodes_created, relationships_created)
            ingestion_job.status_metadata = metadata_state.to_dict()
            ingestion_job.save()
            
    def get_chunk_processing_stats(self, ingestion_job: DataIngestion):
        """Get statistics about chunk processing times
        
        Args:
            ingestion_job: The DataIngestion model instance
            
        Returns:
            dict: Dictionary containing chunk processing statistics
        """
        from data_processing.models import DataIngestionPartition
        
        # Get all partitions for this job
        partitions = DataIngestionPartition.objects.filter(request=ingestion_job)
        
        # Initialize stats
        stats = {
            "total_chunks": partitions.count(),
            "processed_chunks": partitions.filter(status=DataIngestionPartition.STATUS_DONE).count(),
            "failed_chunks": partitions.filter(status=DataIngestionPartition.STATUS_ERROR).count(),
            "pending_chunks": partitions.filter(status=DataIngestionPartition.STATUS_PENDING).count(),
            "processing_chunks": partitions.filter(status=DataIngestionPartition.STATUS_PROCESSING).count(),
            "total_processing_time": 0,
            "avg_processing_time": 0,
            "min_processing_time": float('inf'),
            "max_processing_time": 0,
            "chunks_with_time_data": 0
        }
        
        # Collect timing data from completed and failed partitions
        partitions_with_time = partitions.exclude(processing_time__isnull=True)
        
        for partition in partitions_with_time:
            if partition.processing_time is not None:
                processing_time = partition.processing_time
                stats["chunks_with_time_data"] += 1
                stats["total_processing_time"] += processing_time
                
                # Update min/max times
                if processing_time < stats["min_processing_time"]:
                    stats["min_processing_time"] = processing_time
                if processing_time > stats["max_processing_time"]:
                    stats["max_processing_time"] = processing_time
        
        # Calculate average processing time
        if stats["chunks_with_time_data"] > 0:
            stats["avg_processing_time"] = stats["total_processing_time"] / stats["chunks_with_time_data"]
        else:
            stats["min_processing_time"] = 0  # Reset infinity if no data
            
        return stats
        
    def print_chunk_processing_stats(self, ingestion_job: DataIngestion):
        """Print statistics about chunk processing times
        
        Args:
            ingestion_job: The DataIngestion model instance
        """
        stats = self.get_chunk_processing_stats(ingestion_job)
        
        print("\n===== PARTITION PROCESSING STATISTICS =====")
        print(f"Total partitions: {stats['total_chunks']}")
        print(f"Processed partitions: {stats['processed_chunks']}")
        print(f"Failed partitions: {stats['failed_chunks']}")
        print(f"Pending partitions: {stats['pending_chunks']}")
        print(f"Processing partitions: {stats['processing_chunks']}")
        
        if stats["chunks_with_time_data"] > 0:
            print(f"\nProcessing time statistics (for {stats['chunks_with_time_data']} chunks):")
            print(f"Average processing time: {stats['avg_processing_time']:.2f} seconds")
            print(f"Minimum processing time: {stats['min_processing_time']:.2f} seconds")
            print(f"Maximum processing time: {stats['max_processing_time']:.2f} seconds")
            print(f"Total processing time: {stats['total_processing_time']:.2f} seconds")
        else:
            print("\nNo processing time data available yet")
            
        print("======================================\n")
    
    def _get_prompt_template(self, prompt_name) -> str:
        """Fetch and validate prompt template from Langfuse"""
        try:
            print("\n- Prompt Name", prompt_name)
            prompt_config = self.langfuse_service.get_prompt(prompt_name)
            if not prompt_config:
                raise ValueError(f"Prompt '{prompt_name}' not found in Langfuse")
            if isinstance(prompt_config, dict):
                prompt_template = prompt_config.get('prompt', '')
            else:
                prompt_template = getattr(prompt_config, 'prompt', '')
            # print("\n - Prompt", prompt_template)
            if not prompt_template:
                raise ValueError(f"No prompt template found for '{prompt_name}' in Langfuse")
            logger.add(f"Successfully fetched prompt template from Langfuse")
            return prompt_template
        except Exception as e:
            logger.add(f"Failed to fetch prompt from Langfuse: {str(e)}")
            raise ValueError(f"Failed to fetch prompt from Langfuse: {str(e)}")

    def _setup_neo4j_connection(self):
        credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS, company=self.company)
        credentials_dict = {k: v for d in credentials.value for k, v in d.items()}

        neo4j_username = credentials_dict.get("neo4j_username")
        neo4j_password = credentials_dict.get("neo4j_password")
        neo4j_url = credentials_dict.get("neo4j_url")
        
        try:
            driver = GraphDatabase.driver(
                neo4j_url, 
                auth=(neo4j_username, neo4j_password),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=60,
                connection_timeout=30
            )
            
            # Test connection
            driver.verify_connectivity()
            print("\n==== NEO4J CONNECTION SUCCESSFUL ====\n")
            return driver
            
        except Exception as e:
            print(f"\n==== NEO4J CONNECTION FAILED: {e} ====\n")
            import traceback
            stack_trace = traceback.format_exc()
            traceback.print_exc()
            
            # If we have an active ingestion job, log the connection error
            if hasattr(self, 'current_ingestion_job') and self.current_ingestion_job:
                self._log_destination_error(
                    self.current_ingestion_job,
                    f"Neo4j connection failed: {str(e)}",
                    error_category="connection",
                    is_connection_error=True,
                    stack_trace=stack_trace
                )
            
            raise

    def _handle_error(self, ingestion_job: DataIngestion, error_msg: str, stage: str = None, error_type: str = "error", is_fatal: bool = True, stack_trace: str = None, chunk_id: str = None):
        """Handle errors during ingestion process."""
        # Update the error state
        error_state = self._get_error_state(ingestion_job)
        
        if stage:
            # Add to pipeline errors
            error_state.add_pipeline_error(
                stage=stage,
                error_message=error_msg,
                error_type=error_type,
                is_fatal=is_fatal,
                stack_trace=stack_trace
            )
            
            # Update metadata state
            metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)
            metadata_state.update_pipeline_stage(stage, 'failed')
            ingestion_job.status_metadata = metadata_state.to_dict()
        
        # Save the error state
        ingestion_job.processing_error = error_state.to_dict()
        ingestion_job.status = ingestion_job.STATUS_ERROR
        ingestion_job.save()
        if chunk_id:
            self._update_partition_status(ingestion_job, chunk_id, DataIngestionPartition.STATUS_ERROR, error_msg)
        # Log the error
        print(f"\n error : {error_msg}\n")

    def _update_metadata(self, ingestion_job: DataIngestion, stage: str, status: str):
        """Update ingestion job metadata."""
        if ingestion_job.status_metadata and isinstance(ingestion_job.status_metadata, dict):
            metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)
            metadata_state.update_pipeline_stage(stage, status)
            ingestion_job.status_metadata = metadata_state.to_dict()
            ingestion_job.save()

    def _get_error_state(self, ingestion_job: DataIngestion) -> IngestionErrorState:
        """Get the error state object from the ingestion job"""
        if hasattr(ingestion_job, 'processing_error') and ingestion_job.processing_error:
            if isinstance(ingestion_job.processing_error, dict):
                return self.error_state.from_dict(ingestion_job.processing_error)
            elif isinstance(ingestion_job.processing_error, str):
                return self.error_state.from_json(ingestion_job.processing_error)
        return self.error_state
    
    def _save_error_state(self, ingestion_job: DataIngestion, error_state: IngestionErrorState):
        """Save the error state back to the ingestion job"""
        ingestion_job.processing_error = error_state.to_dict()
        ingestion_job.save()
    
    def _log_error(self, ingestion_job: DataIngestion, error_message: str, stage: str, 
                  error_type: str = "error", is_fatal: bool = False, 
                  stack_trace: str = None, context: dict = None):
        """Log a pipeline error to the error state"""
        error_state = self._get_error_state(ingestion_job)
        error_state.add_pipeline_error(
            stage=stage,
            error_message=error_message,
            error_type=error_type,
            is_fatal=is_fatal,
            stack_trace=stack_trace,
            context=context
        )
        self._save_error_state(ingestion_job, error_state)
    
    def _log_partition_error(self, ingestion_job: DataIngestion, partition_id: str, error_message: str, 
                        error_type: str = "processing", is_fatal: bool = False, 
                        stack_trace: str = None, recoverable: bool = True, 
                        retry_count: int = None, metadata: dict = None):
        """Log a partition-specific error to the partition model"""
        try:
            from data_processing.models import DataIngestionPartition
            partition = DataIngestionPartition.objects.get(id=partition_id)
            
            # Create detailed error message including all information
            detailed_error = f"Error Type: {error_type}\n"
            detailed_error += f"Message: {error_message}\n"
            detailed_error += f"Fatal: {is_fatal}\n"
            detailed_error += f"Recoverable: {recoverable}\n"
            
            if retry_count is not None:
                detailed_error += f"Retry Count: {retry_count}\n"
                
            if stack_trace:
                detailed_error += f"Stack Trace:\n{stack_trace}\n"
                
            if metadata:
                detailed_error += f"Additional Metadata:\n{json.dumps(metadata, indent=2)}"
            
            # Update partition status and error message
            partition.status = DataIngestionPartition.STATUS_ERROR
            partition.error_message = detailed_error
            partition.save()
            
            # Also log to the general error state for backward compatibility
            error_state = self._get_error_state(ingestion_job)
            error_state.add_pipeline_error(
                stage="processing",
                error_message=f"Error in partition {partition_id}: {error_message}",
                error_type="error",
                is_fatal=is_fatal,
                stack_trace=stack_trace,
                context={"partition_id": partition_id, "error_type": error_type}
            )
            self._save_error_state(ingestion_job, error_state)
            
        except Exception as e:
            print(f"Error updating partition error details: {str(e)}")
    
    def _log_schema_error(self, ingestion_job: DataIngestion, error_message: str, error_type: str = "validation",
                         field_name: str = None, is_fatal: bool = False, 
                         schema_fragment: dict = None, metadata: dict = None):
        """Log a schema-related error to the error state"""
        error_state = self._get_error_state(ingestion_job)
        error_state.add_schema_error(
            error_message=error_message,
            error_type=error_type,
            field_name=field_name,
            is_fatal=is_fatal,
            schema_fragment=schema_fragment,
            metadata=metadata
        )
        self._save_error_state(ingestion_job, error_state)
    
    def _log_destination_error(self, ingestion_job: DataIngestion, error_message: str, 
                              chunk_id: str = None, error_category: str = "write",
                              is_connection_error: bool = False, operation_type: str = None,
                              query: str = None, affected_data: any = None, metadata: dict = None,
                              stack_trace: str = None):
        """Log a destination-related error to the error state and partition model
        
        Args:
            ingestion_job: The DataIngestion model instance
            error_message: Description of the error
            chunk_id: Optional ID of the chunk with the error
            error_category: Category of error ('connection', 'write', 'query')
            is_connection_error: Whether this is a connection error
            operation_type: Optional type of operation being performed
            query: Optional query that was being executed
            affected_data: Optional data that was being written/queried
            metadata: Optional additional metadata about the error
            stack_trace: Optional stack trace for the error
        """
        error_state = self._get_error_state(ingestion_job)
        print(f"\n previous error state : {error_state} \n")
        print(f"\n adding destination error \n")
        
        # Add to destination errors in the error state
        error_state.add_destination_error(
            error_message=error_message,
            error_category=error_category,
            is_connection_error=is_connection_error,
            operation_type=operation_type,
            query=query,
            affected_data=affected_data,
            metadata=metadata
        )
        
        # Also add to the metadata format for backwards compatibility
        if ingestion_job.status_metadata and isinstance(ingestion_job.status_metadata, dict):
            metadata_state = self.metadata_state.from_dict(ingestion_job.status_metadata)
            
            # Update pipeline stage if this is a connection error
            if is_connection_error:
                current_stage = metadata_state.pipeline_status.get("current_stage")
                if current_stage == "knowledge_graph_creation":
                    metadata_state.update_pipeline_stage("knowledge_graph_creation", "failed")
                elif current_stage == "destination_export":
                    metadata_state.update_pipeline_stage("destination_export", "failed")
            
            ingestion_job.status_metadata = metadata_state.to_dict()
        
        # If this is a fatal connection error, also log it as a pipeline error
        if is_connection_error and error_category == "connection":
            stage = "knowledge_graph_creation"
            error_state.add_pipeline_error(
                stage=stage,
                error_message=f"Connection error: {error_message}",
                error_type="connection_error",
                is_fatal=True,
                stack_trace=stack_trace
            )
            
            # Update job status to error for connection issues
            ingestion_job.status = ingestion_job.STATUS_ERROR
        
        # Also update the partition model if chunk_id is provided
        if chunk_id:
            try:
                partition = DataIngestionPartition.objects.get(id=chunk_id, request=ingestion_job)
                
                # Create detailed error message
                detailed_error = f"Destination Error ({error_category}):\n"
                detailed_error += f"Message: {error_message}\n"
                
                if operation_type:
                    detailed_error += f"Operation: {operation_type}\n"
                    
                if query:
                    detailed_error += f"Query: {query}\n"
                    
                if stack_trace:
                    detailed_error += f"Stack Trace:\n{stack_trace}\n"
                    
                if metadata:
                    detailed_error += f"Additional Metadata:\n{json.dumps(metadata, indent=2)}"
                
                # Update partition status and error message
                partition.status = DataIngestionPartition.STATUS_ERROR
                if partition.error_message and partition.error_message.strip():
                    partition.error_message += detailed_error
                else:
                    partition.error_message = detailed_error
                partition.save()
                
            except Exception as e:
                print(f"Error updating partition for destination error: {str(e)}")
        
        self._save_error_state(ingestion_job, error_state)
    
    def _log_validation_error(self, ingestion_job: DataIngestion, error_message: str, 
                             error_type: str = "data_type", field_name: str = None,
                             expected_value: any = None, actual_value: any = None,
                             chunk_id: str = None, metadata: dict = None):
        """Log a data validation error to the error state and partition model"""
        error_state = self._get_error_state(ingestion_job)
        error_state.add_validation_error(
            error_message=error_message,
            error_type=error_type,
            field_name=field_name,
            expected_value=expected_value,
            actual_value=actual_value,
            chunk_id=chunk_id,
            metadata=metadata
        )
        
        # Also update the partition model if chunk_id is provided
        if chunk_id:
            try:
                from data_processing.models import DataIngestionPartition
                partition = DataIngestionPartition.objects.get(id=chunk_id, request=ingestion_job)
                
                # Create detailed error message
                detailed_error = f"Validation Error ({error_type}):\n"
                detailed_error += f"Message: {error_message}\n"
                
                if field_name:
                    detailed_error += f"Field: {field_name}\n"
                    
                if expected_value is not None:
                    detailed_error += f"Expected: {expected_value}\n"
                    
                if actual_value is not None:
                    detailed_error += f"Actual: {actual_value}\n"
                    
                if metadata:
                    detailed_error += f"Additional Metadata:\n{json.dumps(metadata, indent=2)}"
                
                # Update partition status and error message
                partition.status = DataIngestionPartition.STATUS_ERROR
                partition.error_message = detailed_error
                partition.save()
                
            except Exception as e:
                print(f"Error updating partition for validation error: {str(e)}")
        
        self._save_error_state(ingestion_job, error_state)
    
    def get_error_summary(self, ingestion_job: DataIngestion) -> dict:
        """Get a summary of all errors for the ingestion job"""
        error_state = self._get_error_state(ingestion_job)
        summary = error_state.get_error_summary()
        
        # Add error count by type for more detailed reporting
        error_counts = error_state.get_error_count_by_type()
        summary["error_counts_by_type"] = error_counts
        
        return summary
    
    def get_recent_errors(self, ingestion_job: DataIngestion, count: int = 5, category: str = None) -> list:
        """Get the most recent errors across all categories or filtered by category
        
        Args:
            ingestion_job: The DataIngestion model instance
            count: Number of errors to retrieve
            category: Optional category to filter by ('pipeline', 'chunk', 'schema', 'destination', 'validation')
            
        Returns:
            list: List of recent errors
        """
        error_state = self._get_error_state(ingestion_job)
        errors = error_state.get_most_recent_errors(count)
        
        # Filter by category if specified
        if category:
            errors = [e for e in errors if e.get("category") == category]
            
        return errors
    
    def _update_partition_status(self, ingestion_job, partition_id, status, error_message=None):
        """
        Update the status of a partition record associated with a chunk
        
        Args:
            ingestion_job: DataIngestion model instance
            chunk_id: The chunk ID or chunk number
            status: New status for the partition (pending, processing, done, error)
            error_message: Optional error message for failed partitions
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:

            target_partition = DataIngestionPartition.objects.filter(id=partition_id).first()
            
            # If partition found, update its status
            if target_partition:
                # Calculate processing time if completing or erroring
                if status in [DataIngestionPartition.STATUS_DONE, DataIngestionPartition.STATUS_ERROR]:
                    if hasattr(target_partition, 'started_at') and target_partition.started_at:
                        processing_time = (timezone.now() - target_partition.started_at).total_seconds()
                        target_partition.processing_time = processing_time
                
                # Set status and timestamps
                target_partition.status = status
                
                if status == DataIngestionPartition.STATUS_PROCESSING and hasattr(target_partition, 'started_at'):
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
                
                target_partition.save()
                print(f"Updated partition {target_partition.id} status to {status}")
                return True
            else:
                print(f"No partition found for chunk {partition_id}")
                return False
                
        except Exception as e:
            print(f"Error updating partition status: {str(e)}")
            import traceback
            traceback.print_exc()
            return False