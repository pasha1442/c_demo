import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from django.utils import timezone


class IngestionMetadataState:
    """
    Class to manage and manipulate the metadata state for data ingestion jobs.
    This provides a structured way to interact with the metadata and simplifies
    operations like updating status, tracking chunks, and managing pipeline stages.
    """

    def __init__(
        self,
        pipeline_status: Optional[Dict[str, Any]] = None,
        schema_metadata: Optional[Dict[str, Any]] = None,
        destination_metadata: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the IngestionMetadataState with provided or default values.
        
        Args:
            pipeline_status: Dictionary containing pipeline status information
            schema_metadata: Dictionary containing schema generation metadata
            destination_metadata: Dictionary containing destination-specific metadata
            schema: Dictionary containing the generated schema
            additional_metadata: Any additional metadata to include
        """
        # Initialize pipeline status
        self.pipeline_status = pipeline_status or {
            "current_stage": "initialization",
            "status": "in_progress",
            "started_at": timezone.now().isoformat(),
            "updated_at": timezone.now().isoformat(),
            "stages": {
                "initialization": {
                    "status": "completed",
                    "started_at": timezone.now().isoformat(),
                    "completed_at": timezone.now().isoformat()
                },
                "chunking": {
                    "status": "completed",
                    "started_at": None,
                    "completed_at": None
                },
                "schema_generation": {
                    "status": "completed",
                    "started_at": None,
                    "completed_at": None
                },
                "processing": {
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None
                },
                "knowledge_graph_creation": {
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None
                }
            }
        }
        
        # Initialize schema metadata
        self.schema_metadata = schema_metadata or {
            "created": False,
            "status": "pending",
            "created_at": None,
            "updated_at": None,
            "error": None
        }
        
        # Initialize destination metadata
        self.destination_metadata = destination_metadata or {
            "type": None,  # e.g., "neo4j", "postgres", etc.
            "connection_info": {},
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": []
        }
        
        # Initialize schema
        self.schema = schema or {}
        
        # Initialize additional metadata
        self.additional_metadata = additional_metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the state to a dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the state
        """
        return {
            "pipeline_status": self.pipeline_status,
            "schema_metadata": self.schema_metadata,
            "destination_metadata": self.destination_metadata,
            "schema": self.schema,
            **self.additional_metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IngestionMetadataState':
        """
        Create an IngestionMetadataState instance from a dictionary.
        
        Args:
            data: Dictionary containing metadata state
            
        Returns:
            IngestionMetadataState: New instance with the provided data
        """
        # Extract known fields
        pipeline_status = data.get("pipeline_status", {})
        schema_metadata = data.get("schema_metadata", {})
        destination_metadata = data.get("destination_metadata", {})
        
        # Handle schema field - ensure it's a proper dictionary
        schema = data.get("schema", {})
        if isinstance(schema, str):
            try:
                # If schema is a JSON string, parse it
                schema = json.loads(schema)
            except json.JSONDecodeError:
                # If it's not valid JSON, keep it as is
                pass
        
        # Any remaining fields go into additional_metadata
        additional_metadata = {k: v for k, v in data.items() if k not in [
            "pipeline_status", "schema_metadata", 
            "destination_metadata", "schema"
        ]}
        
        return cls(
            pipeline_status=pipeline_status,
            schema_metadata=schema_metadata,
            destination_metadata=destination_metadata,
            schema=schema,
            additional_metadata=additional_metadata
        )

    def update_pipeline_stage(self, stage: str, status: str) -> None:
        """
        Update the status of a pipeline stage.
        
        Args:
            stage: Name of the stage to update
            status: New status (e.g., 'pending', 'in_progress', 'completed', 'failed')
        """
        if stage not in self.pipeline_status["stages"]:
            raise ValueError(f"Invalid pipeline stage: {stage}")
            
        now = timezone.now().isoformat()
        
        # Update the stage status
        self.pipeline_status["stages"][stage]["status"] = status
        
        # Update timestamps based on status
        if status == "in_progress" and not self.pipeline_status["stages"][stage]["started_at"]:
            self.pipeline_status["stages"][stage]["started_at"] = now
        
        if status in ["completed", "failed"]:
            self.pipeline_status["stages"][stage]["completed_at"] = now
        
        # Update current stage if needed
        if status == "in_progress":
            self.pipeline_status["current_stage"] = stage
        
        # Update overall pipeline status timestamp
        self.pipeline_status["updated_at"] = now        

    def update_schema(self, schema: Dict[str, Any], status: str = "completed") -> None:
        """
        Update the schema and schema metadata.
        
        Args:
            schema: The schema to set
            status: Status of schema generation (e.g., 'completed', 'failed')
        """
        now = timezone.now().isoformat()
        
        # Ensure schema is a proper dictionary, not a string
        if isinstance(schema, str):
            try:
                schema = json.loads(schema)
            except json.JSONDecodeError:
                # If it's not valid JSON, keep it as is
                pass
                
        self.schema = schema
        self.schema_metadata["created"] = (status == "completed")
        self.schema_metadata["status"] = status
        
        if not self.schema_metadata["created_at"]:
            self.schema_metadata["created_at"] = now
            
        self.schema_metadata["updated_at"] = now

    def update_destination_stats(self, nodes_created: int = 0, relationships_created: int = 0) -> None:
        """
        Update destination statistics.
        
        Args:
            nodes_created: Number of nodes created
            relationships_created: Number of relationships created
        """
        self.destination_metadata["nodes_created"] += nodes_created
        self.destination_metadata["relationships_created"] += relationships_created

    def to_json(self) -> str:
        """
        Convert the state to a JSON string.
        
        Returns:
            str: JSON representation of the state
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'IngestionMetadataState':
        """
        Create an IngestionMetadataState instance from a JSON string.
        
        Args:
            json_str: JSON string containing metadata state
            
        Returns:
            IngestionMetadataState: New instance with the provided data
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
