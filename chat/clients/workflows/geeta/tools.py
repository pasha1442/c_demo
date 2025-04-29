import random
from typing import Annotated
from langchain_core.tools import tool
from chat.retriever.neo4j_retriever import Neo4jRetriever
from langfuse.decorators import observe
from chat.retriever.neo4j_retriever import Neo4jRetriever 
from chat.retriever.whyhowai_retriever import WhyHowAIRetriever
from chat.retriever.pinecone_retriever import PineconeRetriever
from langgraph.prebuilt import InjectedState
from langfuse.decorators import observe
from backend.logger import Logger

from basics.custom_exception import WhyHowAIConnectionError, WhyHowAIDataRetrievalError, Neo4jConnectionError, Neo4jDataRetrievalError, PineconeConnectionError, PineconeDataRetrievalError

workflow_logger = Logger(Logger.WORKFLOW_LOG)

@tool()
@observe()
def knowledge_retriver(query:str, topk:int, state: Annotated[dict, InjectedState], data_source:str="pinecone") -> str:

    """
    Retrieves data from the pinecone index

    Args:
        query : string value for retrieving relevant data
        topk : top k results
    """
    # try: 
    workflow_logger.add(f"Knowledge-Retriever -> (tool) -> : data_source - {data_source}")
    company = state["company"]

    if data_source == "pinecone" : 


        retriever = PineconeRetriever(data_source, company)
        info = retriever.query(query)
        return info


    elif data_source == "kg_neo4j":
        
        obj = Neo4jRetriever(data_source, company)
        info = obj.query(query)
        return info

    elif data_source == "whyhowai":
        
        obj = WhyHowAIRetriever(data_source, company)
        info = obj.query(query)
        return info

    
@tool
@observe()
def recommend_books(query:str, topk:int) -> str:
    """
    Recommend books

    Args:
        query : string value for retrieving relevant data
        topk : top k results
    """
    result = """
    Here are the recommended books, only provide from this not others
    1. Bhagavad-gītā As It Is
    2. The yoga of the Bhagavad Gita
    3. Srimad Bhagvad Gita English
    """
    return result