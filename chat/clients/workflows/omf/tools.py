from langchain_core.tools import tool
from backend.constants import CURRENT_API_COMPANY
from basics.utils import Registry
from chat import utils
from chat.retriever.neo4j_retriever import Neo4jRetriever
from chat.retriever.pinecone_retriever import PineconeRetriever
from chat.workflow_utils import get_context

@tool
def get_latest_updates() -> str:
    """
    Gets latest updates about the borrower/customer from the database.

    Args:
        query : query of the user
    """
    try:
        context = get_context()
        Registry().set(CURRENT_API_COMPANY, context.company)
        
        history = utils.fetch_session_history(context.mobile)
        return f"Here are the latest updates about the borrower/customer : \n{history}"
    except Exception as e:
        print(f"Failed to fetch information from db: {str(e)}")
        return "No new updates for this customer"

@tool
def knowledge_retriver(query, topk, data_source="pinecone") -> str:
    """
    Retrieves data from the pinecone index

    Args:
        query : string value for retrieving relevant data
        topk : top k results
    """
    try: 

        print("\n\ndata source - ", data_source, "\n\n")
        context = get_context()
        Registry().set(CURRENT_API_COMPANY, context.company)
        
        if data_source == "pinecone" : 


            retriever = PineconeRetriever(data_source, context.company)
            info = retriever.query(query)
            return info


        elif data_source == "kg_neo4j":
            
            obj = Neo4jRetriever(data_source)
            info = obj.query(query)
            return info


    except Exception as e:
        print(f"Failed to get data. Error {e}")
        return f"Failed to get data. Error {e}"
