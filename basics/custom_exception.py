import traceback
import sys
from backend.logger import Logger

workflow_logger = Logger(Logger.WORKFLOW_LOG)
error_logger = Logger(Logger.ERROR_LOG)


class BaseException(Exception):
    """Base exception for the workflow-related errors."""

    def __init__(self, message="An error occurred in the workflow"):
        self.message = message
        tb = sys.exc_info()[2]
        if tb:
            trace_lines = traceback.format_tb(tb)
        else:
            trace_lines = ["could not find tracback"]

        error_logger.add(f"Error : {self.message} Traceback : {trace_lines}")
        super().__init__(self.message)


class PromptNotFoundException(BaseException):
    """Exception raised when a required prompt is not found."""

    def __init__(self, message="Prompt not found"):
        self.message = message
        super().__init__(self.message)


class LangfuseConnectionException(BaseException):
    """Exception raised when there is a connection issue with Langfuse."""

    def __init__(self, message="Unable to connect to Langfuse"):
        self.message = message
        super().__init__(self.message)


class WorkflowCreationException(BaseException):
    """Exception raised when there is an error creating a workflow."""

    def __init__(self, message="Error occurred during workflow creation"):
        self.message = message
        super().__init__(self.message)


class WorkflowExecutorException(BaseException):
    """Exception raised when there is an error executing the workflow."""

    def __init__(self, message="Error occurred during workflow execution"):
        self.message = message
        super().__init__(self.message)


class CompanyNotFoundException(BaseException):
    """Exception raised when company not found."""

    def __init__(self, message="Company not found"):
        self.message = message
        super().__init__(self.message)


class LlmExecutionException(BaseException):
    """Exception raised when company not found."""

    def __init__(self, message="Unable to get response from llm."):
        self.message = message
        super().__init__(self.message)


class PineconeConnectionError(BaseException):
    """Exception raised when pinecone connection could not be made"""

    def __init__(self, message="Could not connect with pinecone data source"):
        self.message = message
        super().__init__(self.message)


class Neo4jConnectionError(BaseException):
    """Exception raised when neo4j connection could not be made"""

    def __init__(self, message="Could not connect with neo4j data source"):
        self.message = message
        super().__init__(self.message)


class WhyHowAIConnectionError(BaseException):
    """Exception raised when whyhowai connection could not be made"""

    def __init__(self, message="Could not connect with whyhowai data source"):
        self.message = message
        super().__init__(self.message)




class PineconeDataRetrievalError(BaseException):
    """Exception raised when could not retrieve data from pinecone """

    def __init__(self, message="Error while retrieving the data from Pinecone"):
        self.message = message
        super().__init__(self.message)


class Neo4jDataRetrievalError(BaseException):
    """Exception raised when could not retrieve data from neo4j """

    def __init__(self, message="Error while retrieving the data from Neo4J"):
        self.message = message
        super().__init__(self.message)


class WhyHowAIDataRetrievalError(BaseException):
    """Exception raised when could not retrieve data from whyhowai """

    def __init__(self, message="Error while retrieving the data from WhyHowAI"):
        self.message = message
        super().__init__(self.message)

class IncorrectSurveyError(BaseException):
    """Exception raised when incorrect/empty survey id used to initiate a qdegree survey """

    def __init__(self, message="Could not find a valid survey id"):
        self.message = message
        super().__init__(self.message)


class SQLDBConnectionError(BaseException):
    """Exception raised when sql db api call can not be made"""

    def __init__(self, message="Could not connect with SQL data source"):
        self.message = message
        super().__init__(self.message)


class SQLDataRetrievalError(BaseException):
    """Exception raised when could not retrieve data from sql data source """

    def __init__(self, message="Error while retrieving the data from sql api call"):
        self.message = message
        super().__init__(self.message)

class APIConnectionError(BaseException):
    """Exception raised when could not retrieve data from api agent """

    def __init__(self, message="Error occured while calling the api. Check the auth token and url correctly"):
        self.message = message
        super().__init__(self.message)

class QdrantError(BaseException):
    """Base class for all Qdrant-related errors."""
    pass

class QdrantConnectionError(QdrantError):
    """Exception raised when qdrant connection could not be made"""
    def __init__(self, message="Could not connect with qdrant data source"):
        self.message = message
        super().__init__(self.message)

class QdrantDataRetrievalError(QdrantError):
    """Exception raised when could not retrieve data from qdrant """
    def __init__(self, message="Error while retrieving the data from Qdrant"):
        self.message = message
        super().__init__(self.message)
