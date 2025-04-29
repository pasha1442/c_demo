from typing import List
import pinecone
from chat.graph_workflow import tool
import chat.utils as utils


@tool
def search_geeta_archives(query: str) -> str:
    """
    Search the Geeta archives using the given query.

    Args:
    query (str): The search query.

    Returns:
    str: A string containing the concatenated metadata of the top k matches.
    """
    try:
        query_embedding = utils.create_embedding(query)
        # print(query_embedding)
        vectordb_host = "pinecone" # utils.get_vectordb_host()
        # print(vectordb_host)
        pinecone.init(
            api_key = "", # type: ignore
            environment = "gcp-starter" # type: ignore
        )
        # vector_db_init = utils.init_vectordb_host(vectordb_host)
        vector_db_init = "geeta"
        # print(vector_db_init)
        if not vector_db_init:
            raise Exception("Failed to initialize vector database")
        
        index = pinecone.Index(vector_db_init)
        response = index.query(vector=query_embedding, top_k=2, include_metadata=True)
        matches = response['matches']
        
        info = []
        for match in matches:
            data = match['metadata']
            match_info = ' '.join(f"{key}: {value}" for key, value in data.items())
            info.append(match_info)
        
        return '\n'.join(info)
    except Exception as e:
        return f"An error occurred while searching Geeta archives: {str(e)}"
