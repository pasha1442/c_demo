from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings
from langchain.prompts.chat import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain.chains.openai_functions import create_structured_output_chain
from langchain.chat_models import ChatOpenAI
from langchain_community.vectorstores.neo4j_vector import remove_lucene_chars
from typing import List
from llama_index.graph_stores.neo4j import Neo4jPGStore
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from llama_index.graph_stores.neo4j import Neo4jPGStore
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from company.models import Company, CompanyCustomer, CompanyEntity, CompanyPostProcessing, CompanySetting
from decouple import config
import logging
import wikipedia
import time
from langchain_community.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
from langchain_core.prompts.prompt import PromptTemplate
from chat.assistants import get_active_prompt_from_langfuse
import os
from basics.custom_exception import Neo4jConnectionError, Neo4jDataRetrievalError
from neo4j import GraphDatabase
import nest_asyncio


class Neo4jFactory:
    neo4j_connection_instances = {}

    node_properties_query = """
        CALL apoc.meta.data()
        YIELD label, other, elementType, type, property
        WHERE NOT type = "RELATIONSHIP" AND elementType = "node"
        WITH label AS nodeLabels, collect(property) AS properties
        RETURN {labels: nodeLabels, properties: properties} AS output

        """

    rel_properties_query = """
        CALL apoc.meta.data()
        YIELD label, other, elementType, type, property
        WHERE NOT type = "RELATIONSHIP" AND elementType = "relationship"
        WITH label AS nodeLabels, collect(property) AS properties
        RETURN {type: nodeLabels, properties: properties} AS output
        """

    rel_query = """
        // Step 1: Retrieve top 100 relationships by frequency
        MATCH ()-[r]->()
        WITH type(r) AS relationshipType, count(r) AS frequency
        ORDER BY frequency DESC
        LIMIT 100
        WITH collect({type: relationshipType, frequency: frequency}) AS topRelationships

        // Step 2: Fetch schema information and join with top relationships
        CALL apoc.meta.data()
        YIELD label, other, elementType, type, property
        WHERE type = "RELATIONSHIP" AND elementType = "node"

        // Step 3: Join the schema info with the top relationships
        WITH {source: label, relationship: property, target: other} AS schemaInfo, topRelationships
        UNWIND topRelationships AS topRelationship

        // Step 4: Filter and return results
        WITH schemaInfo, topRelationship
        WHERE schemaInfo.relationship = topRelationship.type
        RETURN schemaInfo, topRelationship.frequency AS frequency
        ORDER BY frequency DESC
         """

    schema_template = """
        This is the schema representation of the Neo4j database.
        Node properties are the following:
        {node_props}
        Relationship properties are the following:
        {rel_props}
        Relationship point from source to target nodes
        {rels}
        Make sure to respect relationship types and directions
        """

    def __init__(self, company):
        start_time = time.time()
        if company:
            self.company = company
            self.credentials = CompanySetting.without_company_objects.get(key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS, company=company)
        else:
            self.company = None
            self.credentials = CompanySetting.objects.get(key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS)

        self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}

        self.neo4j_username = self.credentials_dict.get("neo4j_username")  ## load it from env
        self.neo4j_password = self.credentials_dict.get("neo4j_password")
        self.neo4j_url = self.credentials_dict.get("neo4j_url")

        self.graph = Neo4jGraph(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password,
            enhanced_schema=True,
        )

        self.neo4j_driver = GraphDatabase.driver(self.neo4j_url, auth=(self.neo4j_username, self.neo4j_password))

    @classmethod
    def get_neo4j_instance(cls, company):

        if company.name in cls.neo4j_connection_instances:
            return cls.neo4j_connection_instances[company.name]


        else:
            obj = cls(company)
            cls.neo4j_connection_instances[company.name] = obj
            return obj

    def query_database(self, neo4j_query):
        with self.neo4j_driver.session() as session:
            result = session.run(neo4j_query)
            output = [r.values() for r in result]
            output.insert(0, result.keys())
            return output

    def get_schema(self):

        node_props = self.query_database(self.node_properties_query)
        rel_props = self.query_database(self.rel_properties_query)
        rels = self.query_database(self.rel_query)

        return self.schema_template.format(**{"node_props": node_props, "rel_props": rel_props, "rels": rels})
