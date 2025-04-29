from langchain_core.tools import tool
from backend.constants import CURRENT_API_COMPANY
from basics.utils import Registry
from chat import utils
import pinecone
from chat.workflow_utils import get_context

@tool
def search_document_archive(query: str) -> str:
    """
    Searches the document archive for information realted to user query

    Args:
        query : query of the user
    """
    try:
        context = get_context()
        Registry().set(CURRENT_API_COMPANY, context.company)
        query_embedding = utils.create_embedding(query)
        vectordb_host = utils.get_vectordb_host()
        vector_db_init = utils.init_vectordb_host(vectordb_host)
        if not (vector_db_init):
            #raise exception
            pass
        
        index = pinecone.Index(vector_db_init.get('index'))
        namespace = vector_db_init.get('namespace')
        if namespace:
            response = index.query(vector=query_embedding,top_k=2, include_metadata=True, namespace=namespace)
        else:
            response = index.query(vector=query_embedding,top_k=2, include_metadata=True)
        matches = response['matches']
        info = ''
        for match in matches:
            info += match['metadata']['text']

        return f"Information found in the archive : {info}"
    except Exception as e:
        print(f"Failed to fetch information from db: {str(e)}")
        return f"Failed to execute. Error: {repr(e)}"

@tool
def search_catalogue_for_recommendations(query: str) -> str:
    """
    Searches the catalogue for products that can be recommended to the customer

    Args:
        query : query of the user
    """
    context = get_context()
    Registry().set(CURRENT_API_COMPANY, context.company)

    mobile = context.mobile

    extra_save_data = {
        'function_name': 'search_catalogue_for_recommendations'
    }
    all_save_data = context.extra_save_data | extra_save_data

    avaialable_products = [
        {
            'policy_name' : 'Iprotect Smart',
            'policy_type' : 'Term life insurance',
        }
    ]
    # utils.save_conversation("hi",'function',context.mobile,f"Succesfully sent template on whatsapp, template_id: {template_id}, query: {query}",all_save_data)

    # Todo actual code
    # return f"Succesfully sent template on whatsapp, template_id: {template_id}, query: {query}, FINISH your response and wait for the user to answer the question, your response is not required, since the user will read the question through templated message. only respond with FINAL ANSWER"
    return f"Available products in our catalogue as per user query : {avaialable_products}"