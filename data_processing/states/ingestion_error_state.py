import json, ast
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone


class IngestionErrorState:
    """
    Class to manage and manipulate the error state for data ingestion jobs.
    This provides a structured way to track, categorize, and analyze errors
    that occur during the ingestion pipeline, simplifying troubleshooting
    and providing insights into failure patterns.
    """

    def __init__(
        self,
        pipeline_errors: Optional[Dict[str, Any]] = None,
        schema_errors: Optional[Dict[str, Any]] = None,
        destination_errors: Optional[Dict[str, Any]] = None,
        validation_errors: Optional[Dict[str, Any]] = None,
        additional_error_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the IngestionErrorState with provided or default values.
        
        Args:
            pipeline_errors: Dictionary containing general pipeline errors
            schema_errors: Dictionary containing schema generation errors
            destination_errors: Dictionary containing destination-related errors
            validation_errors: Dictionary containing data validation errors
            additional_error_metadata: Any additional error metadata to include
        """
        # Initialize pipeline errors tracking
        self.pipeline_errors = pipeline_errors or {
            "total_errors": 0,
            "fatal_errors": 0,
            "warning_errors": 0,
            "errors_by_stage": {
                "initialization": [],
                "chunking": [],
                "schema_generation": [],
                "processing": [],
                "knowledge_graph_creation": []
            },
            "last_error": None,
            "has_fatal_error": False
        }
        
        # Initialize schema errors tracking
        self.schema_errors = schema_errors or {
            "has_errors": False,
            "total_errors": 0,
            "last_error_at": None,
            "errors": []
        }
        
        # Initialize destination errors tracking
        self.destination_errors = destination_errors or {
            "connection_errors": [],
            "write_errors": [],
            "query_errors": [],
            "total_errors": 0
        }
        
        # Initialize validation errors tracking
        self.validation_errors = validation_errors or {
            "total_errors": 0,
            "data_type_errors": [],
            "constraint_violations": [],
            "missing_required_fields": [],
            "format_errors": []
        }
        
        # Initialize additional error metadata
        self.additional_error_metadata = additional_error_metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the error state to a dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the error state
        """
        return {
            "pipeline_errors": self.pipeline_errors,
            "schema_errors": self.schema_errors,
            "destination_errors": self.destination_errors,
            "validation_errors": self.validation_errors,
            **self.additional_error_metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IngestionErrorState':
        """
        Create an IngestionErrorState instance from a dictionary.
        
        Args:
            data: Dictionary containing error state data
            
        Returns:
            IngestionErrorState: New instance with the provided data
        """
        if isinstance(data, str):
            if data == "null":
                return cls()
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                try:
                    data = ast.literal_eval(data)
                except (SyntaxError, ValueError):
                    return cls()
        
        # Handle None or non-dictionary cases
        if data is None or not isinstance(data, dict):
            return cls()
        # Extract known fields
        pipeline_errors = data.get("pipeline_errors", {})
        schema_errors = data.get("schema_errors", {})
        destination_errors = data.get("destination_errors", {})
        validation_errors = data.get("validation_errors", {})
        
        # Any remaining fields go into additional_error_metadata
        additional_error_metadata = {k: v for k, v in data.items() if k not in [
            "pipeline_errors", "schema_errors", 
            "destination_errors", "validation_errors"
        ]}
        
        return cls(
            pipeline_errors=pipeline_errors,
            schema_errors=schema_errors,
            destination_errors=destination_errors,
            validation_errors=validation_errors,
            additional_error_metadata=additional_error_metadata
        )

    def add_pipeline_error(
        self, 
        stage: str, 
        error_message: str, 
        error_type: str = "error", 
        is_fatal: bool = False,
        stack_trace: Optional[str] = None,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an error that occurred in a pipeline stage.
        
        Args:
            stage: Name of the pipeline stage where the error occurred
            error_message: Description of the error
            error_type: Type of error ('error', 'warning', 'info')
            is_fatal: Whether this error is fatal to the process
            stack_trace: Optional stack trace for the error
            error_code: Optional error code for categorization
            context: Optional dictionary with additional context
        """
        if stage not in self.pipeline_errors["errors_by_stage"]:
            raise ValueError(f"Invalid pipeline stage: {stage}")
            
        now = timezone.now().isoformat()
        
        # Create error entry
        error_entry = {
            "message": error_message,
            "type": error_type,
            "timestamp": now,
            "is_fatal": is_fatal
        }
        
        if stack_trace:
            error_entry["stack_trace"] = stack_trace
            
        if error_code:
            error_entry["error_code"] = error_code
            
        if context:
            error_entry["context"] = context
        
        # Add error to stage errors
        self.pipeline_errors["errors_by_stage"][stage].append(error_entry)
        
        # Update counters
        self.pipeline_errors["total_errors"] += 1
        
        if is_fatal:
            self.pipeline_errors["fatal_errors"] += 1
            self.pipeline_errors["has_fatal_error"] = True
        
        if error_type == "warning":
            self.pipeline_errors["warning_errors"] += 1
        
        # Update last error
        self.pipeline_errors["last_error"] = {
            "stage": stage,
            "message": error_message,
            "timestamp": now,
            "is_fatal": is_fatal
        }



    def add_schema_error(
        self, 
        error_message: str, 
        error_type: str = "validation",
        field_name: Optional[str] = None,
        is_fatal: bool = False,
        schema_fragment: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an error that occurred during schema generation or validation.
        
        Args:
            error_message: Description of the error
            error_type: Type of error (e.g., 'validation', 'generation', 'compatibility')
            field_name: Optional name of the field with the error
            is_fatal: Whether this error is fatal for schema generation
            schema_fragment: Optional fragment of the schema with the issue
            metadata: Optional additional metadata about the error
        """
        now = timezone.now().isoformat()
        
        # Create error entry
        error_entry = {
            "message": error_message,
            "type": error_type,
            "timestamp": now,
            "is_fatal": is_fatal
        }
        
        if field_name:
            error_entry["field_name"] = field_name
            
        if schema_fragment:
            error_entry["schema_fragment"] = schema_fragment
            
        if metadata:
            error_entry["metadata"] = metadata
        
        # Add error to schema errors
        self.schema_errors["errors"].append(error_entry)
        self.schema_errors["total_errors"] += 1
        self.schema_errors["has_errors"] = True
        self.schema_errors["last_error_at"] = now

    def add_destination_error(
        self, 
        error_message: str, 
        error_category: str = "write",
        is_connection_error: bool = False,
        operation_type: Optional[str] = None,
        query: Optional[str] = None,
        affected_data: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an error that occurred with the destination system.
        
        Args:
            error_message: Description of the error
            error_category: Category of error ('connection', 'write', 'query')
            is_connection_error: Whether this is a connection error
            operation_type: Optional type of operation being performed
            query: Optional query that was being executed
            affected_data: Optional data that was being written/queried
            metadata: Optional additional metadata about the error
        """
        now = timezone.now().isoformat()
        
        # Create error entry
        error_entry = {
            "message": error_message,
            "timestamp": now
        }
        
        if operation_type:
            error_entry["operation_type"] = operation_type
            
        if query:
            error_entry["query"] = query
            
        if affected_data:
            error_entry["affected_data"] = affected_data
            
        if metadata:
            error_entry["metadata"] = metadata
        
        # Add error to appropriate category
        if is_connection_error or error_category == "connection":
            self.destination_errors["connection_errors"].append(error_entry)
        elif error_category == "write":
            self.destination_errors["write_errors"].append(error_entry)
        else:
            self.destination_errors["query_errors"].append(error_entry)
        
        print(f"\n destination_errors : {self.destination_errors} \n")
        # Update total errors
            
        self.destination_errors["total_errors"] += 1

    def add_validation_error(
        self, 
        error_message: str, 
        error_type: str = "data_type",
        field_name: Optional[str] = None,
        expected_value: Optional[Any] = None,
        actual_value: Optional[Any] = None,
        partition_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a data validation error.
        
        Args:
            error_message: Description of the error
            error_type: Type of validation error ('data_type', 'constraint', 'missing_field', 'format')
            field_name: Optional name of the field with the error
            expected_value: Optional expected value or pattern
            actual_value: Optional actual value that caused the error
            partition_id: Optional ID of the partition with the validation error
            metadata: Optional additional metadata about the error
        """
        now = timezone.now().isoformat()
        
        # Create error entry
        error_entry = {
            "message": error_message,
            "timestamp": now
        }
        
        if field_name:
            error_entry["field_name"] = field_name
            
        if expected_value is not None:
            error_entry["expected_value"] = expected_value
            
        if actual_value is not None:
            error_entry["actual_value"] = actual_value
            
        if partition_id:
            error_entry["partition_id"] = partition_id
            
        if metadata:
            error_entry["metadata"] = metadata
        
        # Add error to appropriate category
        if error_type == "data_type":
            self.validation_errors["data_type_errors"].append(error_entry)
        elif error_type == "constraint":
            self.validation_errors["constraint_violations"].append(error_entry)
        elif error_type == "missing_field":
            self.validation_errors["missing_required_fields"].append(error_entry)
        elif error_type == "format":
            self.validation_errors["format_errors"].append(error_entry)
        
        # Update total errors
        self.validation_errors["total_errors"] += 1

    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all errors.
        
        Returns:
            Dict[str, Any]: Summary of errors by category
        """
        return {
            "total_errors": (
                self.pipeline_errors["total_errors"] +
                self.destination_errors["total_errors"] +
                self.validation_errors["total_errors"] +
                self.schema_errors["total_errors"]
            ),
            "has_fatal_errors": self.pipeline_errors["has_fatal_error"],
            "total_fatal_errors": self.pipeline_errors["fatal_errors"],
            "error_distribution": {
                "pipeline": self.pipeline_errors["total_errors"],
                "schema": self.schema_errors["total_errors"],
                "destination": self.destination_errors["total_errors"],
                "validation": self.validation_errors["total_errors"]
            }
        }

    def get_most_recent_errors(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get the most recent errors across all categories.
        
        Args:
            count: Number of recent errors to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of the most recent errors
        """
        # Collect all errors with timestamps
        all_errors = []
        
        # Add pipeline errors
        for stage, errors in self.pipeline_errors["errors_by_stage"].items():
            for error in errors:
                all_errors.append({
                    **error,
                    "category": "pipeline",
                    "stage": stage
                })
        
        # Add schema errors
        for error in self.schema_errors["errors"]:
            all_errors.append({
                **error,
                "category": "schema"
            })
        
        # Add destination errors (connection)
        for error in self.destination_errors["connection_errors"]:
            all_errors.append({
                **error,
                "category": "destination",
                "subcategory": "connection"
            })
        
        # Add destination errors (write)
        for error in self.destination_errors["write_errors"]:
            all_errors.append({
                **error,
                "category": "destination",
                "subcategory": "write"
            })
        
        # Add destination errors (query)
        for error in self.destination_errors["query_errors"]:
            all_errors.append({
                **error,
                "category": "destination",
                "subcategory": "query"
            })
        
        # Sort by timestamp (most recent first)
        sorted_errors = sorted(
            all_errors, 
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )
        
        # Return the requested number of errors
        return sorted_errors[:count]

    def get_error_count_by_type(self) -> Dict[str, int]:
        """
        Get counts of errors by type.
        
        Returns:
            Dict[str, int]: Count of each error type
        """
        counts = {
            "pipeline": {
                "total": self.pipeline_errors["total_errors"],
                "fatal": self.pipeline_errors["fatal_errors"],
                "warning": self.pipeline_errors["warning_errors"],
                "by_stage": {
                    stage: len(errors) for stage, errors in 
                    self.pipeline_errors["errors_by_stage"].items()
                }
            },
            "schema": {
                "total": self.schema_errors["total_errors"]
            },
            "destination": {
                "total": self.destination_errors["total_errors"],
                "connection": len(self.destination_errors["connection_errors"]),
                "write": len(self.destination_errors["write_errors"]),
                "query": len(self.destination_errors["query_errors"])
            },
            "validation": {
                "total": self.validation_errors["total_errors"],
                "data_type": len(self.validation_errors["data_type_errors"]),
                "constraint": len(self.validation_errors["constraint_violations"]),
                "missing_field": len(self.validation_errors["missing_required_fields"]),
                "format": len(self.validation_errors["format_errors"])
            }
        }
        
        return counts

    def to_json(self) -> str:
        """
        Convert the error state to a JSON string.
        
        Returns:
            str: JSON representation of the error state
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'IngestionErrorState':
        """
        Create an IngestionErrorState instance from a JSON string.
        
        Args:
            json_str: JSON string containing error state data
            
        Returns:
            IngestionErrorState: New instance with the provided data
        """
        return cls.from_dict(json_str)