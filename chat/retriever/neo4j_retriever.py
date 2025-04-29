# from llama_index.core import Document, PropertyGraphIndex
# from llama_index.core.indices.property_graph import (
#     SimpleLLMPathExtractor,
#     SchemaLLMPathExtractor,
#     DynamicLLMPathExtractor,
# )
# from llama_index.llms.openai import OpenAI
from langchain.prompts.chat import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain.chains.openai_functions import create_structured_output_chain
from langchain.chat_models import ChatOpenAI
from typing import List
from dotenv import load_dotenv
import time
from langchain_core.prompts.prompt import PromptTemplate
from chat.assistants import get_active_prompt_from_langfuse
import os
from basics.custom_exception import Neo4jConnectionError, Neo4jDataRetrievalError
import nest_asyncio
from langfuse.decorators import observe
import re
from chat.workflow_utils import push_llminfo_to_openmeter
from backend.logger import Logger
from chat.retriever.factory.neo4j_factory import Neo4jFactory
from chat.retriever.base_retriever import BaseRetriever
from chat.clients.workflows.agent_state import PipelineState
import traceback
nest_asyncio.apply()
load_dotenv()
import json

workflow_logger = Logger(Logger.WORKFLOW_LOG)



# Extract entities from text
class Entities(BaseModel):
    """Identifying information about entities."""

    names: List[str] = Field(
        ...,
        description="List of names including chapter names, chapter numbers, book names, paragraph details, characters, spiritual concepts, etc."
                    "appear in the text",
    )


class Neo4jRetriever(BaseRetriever):

    def __init__(self, data_source, state):
        try:

            start_time = time.time()
            
            context  = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id
            super().__init__()
            self.database = self.DATABASE_NEO4J 
            self.database_type = self.DATABASE_TYPE_GRAPH_DB

            self.openmeter_obj = context.openmeter
            self.neo4j_connection = Neo4jFactory.get_neo4j_instance(self.company)
            self.data_source = data_source
            self.prompt_info = get_active_prompt_from_langfuse(self.company.id, "knowledge_graph_retriever")
            self.CYPHER_GENERATION_PROMPT = PromptTemplate(
                input_variables=["schema", "question"], template=self.prompt_info["system_prompt"]
            )

            self.dynamic_query_chain = self.CYPHER_GENERATION_PROMPT | ChatOpenAI(temperature=0, model="gpt-4o")

            self.llm_for_search = ChatOpenAI(temperature=0.0, model="gpt-4o")

            self.entity_extraction_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are tasked with extracting different types of chapter books, paragraphs, and chapter details."
                    ),
                    (
                        "human",
                        "Use the given format to extract information from the following input: {question}"
                    ),
                ]
            )

            self.entity_extraction_chain = create_structured_output_chain(Entities, self.llm_for_search,
                                                                          self.entity_extraction_prompt)
            self.graph_schema = self.neo4j_connection.get_schema()







        except Exception as e:
            # print(e)
            raise Neo4jConnectionError(
                f"[{self.company.name}]  ({self.session_id}) - Could not connect with neo4j data source")

    def find_similar_entities(self, question):

        character_search_query = """MATCH (a:character {{text: '{}'}})
        CALL db.index.vector.queryNodes('characterIndex', 3, a.embedding) 
        YIELD node AS similar_character, score
        where score > 0.95
        RETURN a.text, similar_character.text
        """

        entities = self.entity_extraction_chain({"question": question})

        entities = [entity.lower() for entity in entities["function"].names]

        similar_entities = {}
        for entity in entities:
            similar_entities[entity] = [entity]
            for entity_a, entity_b in self.neo4j_connection.query_database(character_search_query.format(entity))[1:]:
                similar_entities[entity].append(entity_b)

        return similar_entities

    def extract_cypher(self, text: str) -> str:
        # The pattern to find Cypher code enclosed in triple backticks
        # print(text)
        text = text.replace("cypher", "")
        pattern = r"```(.*?)```"

        # Find all matches in the input text
        matches = re.findall(pattern, text, re.DOTALL)

        # Extract the first match if available
        if matches:
            return matches[0]

        return text

    def structured_retriever(self, question):

        similar_entities = self.find_similar_entities(question)

        structured_search = self.dynamic_query_chain.invoke({"question": question, "schema": self.graph_schema})

        cypher_query = self.extract_cypher(structured_search.content)

        structured_search_resp = []
        for entity in similar_entities:
            for entity_b in similar_entities[entity]:
                result = self.neo4j_connection.query_database(cypher_query.replace(entity, entity_b))
                structured_search_resp.append(result)

        return structured_search, cypher_query, structured_search_resp

    def unstructured_retriever(self, question: str) -> str:
        cypher_query = f"""CALL db.index.fulltext.queryNodes('vector_search_unstructured', "{question}") 
            YIELD node, score AS sc 
            LIMIT 1

            CALL db.index.vector.queryNodes("kg_retriever_test", 2, node.embedding) 
            YIELD node AS shloka, score 
            WHERE score > 0.95
            RETURN shloka.shloka_name, shloka.shloka_in_sanskrit ,shloka.shloka_purport, shloka.shloka_url
        """

        output = self.neo4j_connection.query_database(cypher_query)

        header = output[0]
        result = ""
        for r_idx, row in enumerate(output[1:]):
            document = f"#Document {r_idx}\n"

            for v_idx, val in enumerate(row):
                document += f"{header[v_idx]}: {val}\n"

            result += document

        return result

    def retriever(self, question: str, is_static=False):
        workflow_logger.add(f"Knowledge-Retriever [{self.company}]  ({self.session_id}) -> (Neo4j) : Search-Query {question}")

        t1 = time.time()

        structured_search, cypher_query, structured_search_resp = self.structured_retriever(question["question"])
        push_llminfo_to_openmeter(node_data={"messages": [structured_search], "llm_info": self.prompt_info},
                                  openmeter_obj=self.openmeter_obj)

        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (Neo4j) : [{round(time.time() - t1, 2)} sec ] fetched results from neo4j graph")

        t2 = time.time()
        unstructured_data = self.unstructured_retriever(question["question"])

        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (Neo4j) : [{round(time.time() - t2, 2)} sec ] fetched results from neo4j vector index")

        final_data = f"""Structured data:
        {structured_search_resp}
        Unstructured data:
        {unstructured_data}
        """

        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}]  ({self.session_id}) -> (Neo4j) : [{round(time.time() - t1, 2)} sec ] Final Search Result {final_data}")
        return final_data

    def query(self, question: str) -> str:
        try:

            _res = self.retriever({"question": question})
            self.push_knowledge_retriever_data_to_openmeter()
            return _res
        except Exception as e:
            raise Neo4jDataRetrievalError(
                f"[{self.company.name}] ({self.session_id})- Could not retrieve data from neo4j data source")
            return None


class AdvancedNeo4jRetriever(BaseRetriever):

    def __init__(self, data_source, state=None, company=None):
        try:

            start_time = time.time()
            context  = PipelineState.get_workflow_context_object_from_state(state)
            self.company = context.company
            self.session_id = context.session_id
            self.openmeter_obj = context.openmeter
            self.neo4j_connection = Neo4jFactory.get_neo4j_instance(self.company)
            self.data_source = data_source
            self.cypher_query_builder_llm_info = get_active_prompt_from_langfuse(self.company.id,
                                                                                 "cypher_query_builder")

            self.CYPHER_GENERATION_PROMPT = PromptTemplate(
                input_variables=["schema", "question"], template=self.cypher_query_builder_llm_info["system_prompt"]
            )
    

            self.cypher_query_chain = cypher_prompt = self.CYPHER_GENERATION_PROMPT | ChatOpenAI(temperature=0,
                                                                                                 model="gpt-4o")

            self.schema = get_active_prompt_from_langfuse(self.company.id, "neo4j_db_schema")["system_prompt"]







        except Exception as e:
            raise Neo4jConnectionError(
                f"[{self.company.name}] ({self.session_id}) - Could not connect with neo4j data source")

    def find_similar_entities(self, question):

        character_search_query = """MATCH (a:character {{text: '{}'}})
        CALL db.index.vector.queryNodes('characterIndex', 3, a.embedding)
        YIELD node AS similar_character, score
        where score > 0.95
        RETURN a.text, similar_character.text
        """

        entities = self.entity_extraction_chain({"question": question})

        entities = [entity.lower() for entity in entities["function"].names]

        similar_entities = {}
        for entity in entities:
            similar_entities[entity] = [entity]
            for entity_a, entity_b in self.neo4j_connection.query_database(character_search_query.format(entity))[1:]:
                similar_entities[entity].append(entity_b)

        return similar_entities

    def extract_cypher(self, text: str) -> str:
        text = text.replace("cypher", "")
        pattern = r"```(.*?)```"

        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            return matches[0]

        return text

    @observe()
    def structured_retriever(self, question: str) -> str:
        structured_search = self.cypher_query_chain.invoke({"question": question, "schema": self.schema})
        cypher_query = self.extract_cypher(structured_search.content)
        structured_search_resp = self.neo4j_connection.query_database(cypher_query)

        return structured_search, cypher_query, structured_search_resp
    
    @observe()
    def unstructured_retriever(self, question):
        """
        Dynamically generates an optimized Cypher query for semantic search 
        based on available vector/fulltext indexes and database schema.
        
        Args:
            question (str): User's natural language query
        
        Returns:
            str: Formatted search results or error message
        """
        
        workflow_logger.add(f"Dynamic Unstructured Retriever [{self.company}] ({self.session_id}) - Query: {question}")
        
        try:
            print("\n[STEP 1] Fetching Available Indexes")
            index_query = """
            SHOW INDEXES
            YIELD name, type, entityType, labelsOrTypes, properties
            WHERE type = 'VECTOR' OR type = 'FULLTEXT'
            RETURN name, type, labelsOrTypes, properties
            """
            
            try:
                indexes = self.neo4j_connection.query_database(index_query)
                print(f"Indexes Found: {len(indexes)-1}")  
                
                for idx in indexes[1:]:
                    print(f"Index Details: {idx}")
            except Exception as index_fetch_error:
                print(f"ERROR FETCHING INDEXES: {index_fetch_error}")
                raise
            
            if not indexes or len(indexes) <= 1:
                print("NO SUITABLE INDEXES FOUND")
                workflow_logger.add("No suitable indexes found for search")
                raise ValueError("No search indexes available")
            
            header = indexes[0]
            index_data = indexes[1:]
            
            vector_indexes = []
            fulltext_indexes = []
            
            print("\n[STEP 2] Organizing Indexes")
            for idx in index_data:
                index_info = {
                    "name": idx[0],
                    "type": idx[1],
                    "labels": idx[2],
                    "properties": idx[3]
                }
                
                if index_info["type"] == "VECTOR":
                    vector_indexes.append(index_info)
                    print(f"VECTOR INDEX: {index_info}")
                elif index_info["type"] == "FULLTEXT":
                    fulltext_indexes.append(index_info)
                    print(f"FULLTEXT INDEX: {index_info}")
            
            vector_indexes_str = json.dumps(vector_indexes, indent=2)
            fulltext_indexes_str = json.dumps(fulltext_indexes, indent=2)
            
            print("\n[STEP 3] Generating Dynamic Cypher Query")
            try:
                vector_search_prompt_info = get_active_prompt_from_langfuse(
                    self.company.id, "vector_search_builder"
                )
                print("LANGFUSE PROMPT RETRIEVED SUCCESSFULLY")
            except Exception as prompt_fetch_error:
                print(f"ERROR FETCHING LANGFUSE PROMPT: {prompt_fetch_error}")
                raise
            
            vector_search_prompt = PromptTemplate(
                input_variables=["schema", "vector_indexes", "fulltext_indexes", "question"], 
                template=vector_search_prompt_info["system_prompt"]
            )
            
            vector_search_chain = vector_search_prompt | ChatOpenAI(
                temperature=0, 
                model="gpt-4o"
            )
            
            prompt_context = {
                "schema": self.schema,
                "vector_indexes": vector_indexes_str,
                "fulltext_indexes": fulltext_indexes_str,
                "question": question
            }
            
            print("\n[STEP 4] Invoking LLM for Query Generation")
            try:
                dynamic_query_result = vector_search_chain.invoke(prompt_context)
                dynamic_query = self.extract_cypher(dynamic_query_result.content)
                
                print("GENERATED CYPHER QUERY:")
                print(dynamic_query)
            except Exception as query_gen_error:
                print(f"ERROR GENERATING QUERY: {query_gen_error}")
                raise
            
            workflow_logger.add(f"Generated Cypher Query: {dynamic_query}")
            
            if hasattr(self, 'openmeter_obj') and self.openmeter_obj:
                push_llminfo_to_openmeter(
                    node_data={
                        "messages": [dynamic_query_result], 
                        "llm_info": vector_search_prompt_info
                    },
                    openmeter_obj=self.openmeter_obj
                )
            
            print("\n[STEP 5] Executing Generated Query")
            try:
                query_result = self.neo4j_connection.query_database(dynamic_query)
                
                
                if query_result and len(query_result) > 1:
                    header = query_result[0]
                    results = query_result[1:]
                    
                    
                    formatted_response = "Search Results:\n\n"
                    for i, result in enumerate(results, 1):
                        formatted_response += f"Result {i}:\n"
                        for j, field in enumerate(header):
                            if result[j] is not None:
                                print(f"  {field}: {result[j]}")
                                formatted_response += f"  {field}: {result[j]}\n"
                        formatted_response += "\n"
                    
                    return formatted_response
                
                raise ValueError("No results found from generated query")
            
            except Exception as execution_error:
                print(f"QUERY EXECUTION ERROR: {execution_error}")
                workflow_logger.add(f"Query execution error: {str(execution_error)}")
                raise
        
        except Exception as overall_error:
            traceback.print_exc()
            
            workflow_logger.add(f"Unstructured retriever error: {str(overall_error)}")
            
            raise Neo4jDataRetrievalError(f"Unstructured retriever error: {str(overall_error)}")
            
    @observe()
    def get_schema(self):
        """
        Fetches the database schema directly from Neo4j and categorizes indexes into vector and fulltext types.
        
        Returns:
            A formatted string containing the database schema and index information
        """
        try:
            t1 = time.time()
            workflow_logger.add(f"Schema Fetcher [{self.company}] ({self.session_id}) -> Fetching schema and indexes directly from Neo4j")
            
            schema = self.neo4j_connection.get_schema()
            print(schema)
            
            index_query = """
            SHOW INDEXES
            YIELD name, type, entityType, labelsOrTypes, properties
            WHERE type = 'VECTOR' OR type = 'FULLTEXT'
            RETURN name, type, labelsOrTypes, properties
            """
            
            indexes = self.neo4j_connection.query_database(index_query)
            
            if not indexes or len(indexes) <= 1:
                return "No suitable indexes found in the database."
            
            header = indexes[0]
            index_data = indexes[1:]
            
            vector_indexes = []
            fulltext_indexes = []
            
            for idx in index_data:
                index_info = {
                    "name": idx[0],
                    "type": idx[1],
                    "labels": idx[2],
                    "properties": idx[3]
                }
                
                if index_info["type"] == "VECTOR":
                    vector_indexes.append(index_info)
                elif index_info["type"] == "FULLTEXT":
                    fulltext_indexes.append(index_info)
            
            formatted_result = "# Neo4j Database Structure\n\n"
            
            formatted_result += "## Database Schema\n\n"
            formatted_result += "```json\n"
            formatted_result += json.dumps(schema, indent=2) 
            formatted_result += "\n```\n\n"
            
            formatted_result += "## Vector Indexes\n\n"
            if vector_indexes:
                formatted_result += "```json\n"
                formatted_result += json.dumps(vector_indexes, indent=2)
                formatted_result += "\n```\n\n"
            else:
                formatted_result += "No vector indexes found.\n\n"
            
            formatted_result += "## Fulltext Indexes\n\n"
            if fulltext_indexes:
                formatted_result += "```json\n"
                formatted_result += json.dumps(fulltext_indexes, indent=2)
                formatted_result += "\n```\n\n"
            else:
                formatted_result += "No fulltext indexes found.\n\n"
            
            execution_time = round(time.time() - t1, 2)
            workflow_logger.add(
                f"Schema Fetcher [{self.company}] ({self.session_id}) -> Completed in {execution_time}s"
            )
            
            return formatted_result
            
        except Exception as e:
            error_msg = f"Error fetching schema and indexes: {str(e)}"
            workflow_logger.add(f"Schema Fetcher [{self.company}] ({self.session_id}) -> Error: {error_msg}")
            traceback.print_exc()
            
            return f"Error fetching database schema and indexes: {str(e)}"
     
    @observe()
    def execute_cypher_query(self, cypher_query: str) -> str:
        """
        Executes a Cypher query and returns formatted results.
        
        Args:
            cypher_query: The Cypher query to execute
            
        Returns:
            Formatted results from the Neo4j query
        """
        t1 = time.time()
        workflow_logger.add(f"Neo4j Executor [{self.company}] ({self.session_id}) -> Query: {cypher_query}")
        
        try:
            result = self.neo4j_connection.query_database(cypher_query)
            
            execution_time = round(time.time() - t1, 2)
            workflow_logger.add(
                f"Neo4j Executor [{self.company}] ({self.session_id}) -> [{execution_time}s] Query executed successfully"
            )
            
            if result and len(result) > 1:
                header = result[0]
                data_rows = result[1:]
                
                formatted_result = "Results:\n\n"
                for i, row in enumerate(data_rows, 1):
                    formatted_result += f"Result {i}:\n"
                    for j, field in enumerate(header):
                        if row[j] is not None:
                            formatted_result += f"  {field}: {row[j]}\n"
                    formatted_result += "\n"
                    
                
                return formatted_result
            elif result and len(result) == 1:
                return "Query executed successfully, but returned no data."
            else:
                return "No results returned from the query."
                
        except Exception as execution_error:
            error_msg = f"Error executing Cypher query: {str(execution_error)}"
            workflow_logger.add(f"Neo4j Executor [{self.company}] ({self.session_id}) -> Error: {error_msg}")
            return f"Error: {str(execution_error)}"

        
    @observe()
    def retriever(self, question: str):
        workflow_logger.add(f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (Neo4j) : Search-Query {question}")

        t1 = time.time()

        structured_search, cypher_query, structured_search_resp = self.structured_retriever(question)
        push_llminfo_to_openmeter(
            node_data={"messages": [structured_search], "llm_info": self.cypher_query_builder_llm_info},
            openmeter_obj=self.openmeter_obj)

        unstructured_search_resp = self.unstructured_retriever(question)

        full_response = f"structured response :\n Cypher Query - {cypher_query}\n Cypher Response - {structured_search_resp}\n Unstructured Response: {unstructured_search_resp}"


        workflow_logger.add(
            f"Knowledge-Retriever [{self.company}] ({self.session_id}) -> (Neo4j) : [{round(time.time() - t1, 2)} sec ] Final Search Result {full_response}")
        return full_response

    def query(self, question: str) -> str:
        print("calling")

        try:
            return self.retriever(question)

        except Exception as e:
            raise Neo4jDataRetrievalError(
                f"[{self.company.name}] ({self.session_id})- Could not retrieve data from neo4j data source")
            return None