from datetime import datetime
import json
from typing import Any, Dict, List, Optional
from basics.utils import UUID
from chat.clients.workflows.agent_state import PipelineState
from chat.vector_databases.base_vector_database import BaseVectorDatabase
from neo4j import GraphDatabase
from asgiref.sync import sync_to_async
from company.models import CompanySetting
from metering.services.openmeter import OpenMeter

class Neo4j(BaseVectorDatabase):
    def __init__(self, company=None, data_source=None, state=None, uri=None, user=None, password=None, openmeter_obj=None):
        self.company = company
        self.data_source = data_source
        if state and "workflow_context" in state:
            context = PipelineState.get_workflow_context_object_from_state(state)
            self.company = self.company or context.company
            self.openmeter_obj = context.openmeter
        self.credentials = CompanySetting.without_company_objects.get(
            key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS, company=self.company
        )
        self.credentials_dict = {k: v for d in self.credentials.value for k, v in d.items()}
        if not user:
            user = self.credentials_dict.get("neo4j_username")
        if not password:
            password = self.credentials_dict.get("neo4j_password")
        if not uri:
            uri = self.credentials_dict.get("neo4j_url")
        if openmeter_obj:
            self.openmeter_obj = openmeter_obj
        else:
            self.openmeter_obj = OpenMeter(company=self.company)
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        from chat.services.long_term_memory_generation_service import LongTermMemoryGenerationService
        self.AGENT = LongTermMemoryGenerationService.LONG_TERM_MEMORY_PROMPT_NAME
        self.database_type = "Neo4j"
        self.database = "Neo4j"

    def _create_label_if_not_exists(self, label: str) -> None:
        pass

    def push(
        self,
        container_name: str,
        vectors: List[List[float]],
        ids: List[Any],
        metadata: List[Dict[str, Any]],
        extra_params: Optional[Dict[str, Any]] = None
    ) -> None:
        self._create_label_if_not_exists(container_name)

        try:
            with self.driver.session() as session:
                if isinstance(metadata, dict): 
                    metadata = [metadata]
                if isinstance(vectors[0], float):
                    vectors = [vectors]
                if isinstance(ids, (int, str)):
                    ids = [ids]
                current_time = datetime.utcnow().isoformat()
                
                for vector, meta in zip(vectors, metadata):
                    user_created = False
                    conversation_created = False

                    try:
                        # data for users label
                        client_identifier = meta.get("client_identifier")
                        user_name = meta.get("user_name","")
                        user_data = json.dumps(meta.get("user_data",{}))

                        session.run(
                            """
                            MERGE (n:users {client_identifier: $client_identifier})
                            SET n.user_name = $user_name,
                                n.user_data = $user_data,
                                n.last_active = $last_active
                            """,
                            client_identifier=client_identifier,
                            user_name=user_name,
                            user_data=user_data,
                            last_active=current_time
                        )
                        user_created = True
                    except Exception as e:
                        print("issue creating user")
                        user_created = False


                    # data for conversations label
                    try:
                        session_id = meta.get("session_id")
                        topic = meta.get("topic","other")
                        sentiment = meta.get("sentiment","neutral")
                        conversation_data = json.dumps(meta.get("conversation_data",{}))
                        client_identifier = meta.get("client_identifier")
                        company_id = meta.get("company_id")
                        conversation_id = str(UUID.get_uuid4())

                        session.run(
                            """
                            CREATE (n:conversations)
                            SET n.embedding = $embedding,
                                n.session_id = $session_id,
                                n.topic = $topic,
                                n.sentiment = $sentiment,
                                n.conversation_data =$conversation_data,
                                n.company_id = $company_id,
                                n.client_identifier = $client_identifier,
                                n.created_at = $created_at,
                                n.conversation_id = $conversation_id
                            """,
                            embedding=vector,
                            session_id=session_id,
                            topic=topic,
                            sentiment=sentiment,
                            conversation_data=conversation_data,
                            company_id=company_id,
                            client_identifier=client_identifier,
                            created_at=current_time,
                            conversation_id=conversation_id
                        )
                        conversation_created = True
                    except Exception as e:
                        print("issue creating conversation")
                        conversation_created = False
                    
                    if user_created and conversation_created:
                        try:
                            session.run(
                                """
                                MATCH (u:users {client_identifier: $client_identifier})
                                MATCH (c:conversations {conversation_id: $conversation_id})
                                MERGE (u)-[:HAD_CONVERSATION]->(c)
                                """,
                                client_identifier=client_identifier,
                                conversation_id=conversation_id
                            )
                        except Exception as e:
                            print("failed")
                    
        except Exception as e:
            print(f"\n Error occurred: {e} \n")
            return False

    
    def query(
        self,
        container_name: str = None,
        query: str = "",
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        extra_params: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        Performs a vector similarity search using vector index.
        Vector Index needs to be created manually on neo4j before using search

        CREATE VECTOR INDEX event_embedding_index 
        FOR (n:Event) ON (n.embedding)
        OPTIONS { 
        indexConfig: { 
            `vector.dimensions`: 1536, 
            `vector.similarity_function`: "cosine" 
        } 
        };

        CREATE VECTOR INDEX profile_attribute_embedding_index 
        FOR (n:ProfileAttribute) ON (n.embedding)
        OPTIONS { 
        indexConfig: { 
            `vector.dimensions`: 1536, 
            `vector.similarity_function`: "cosine" 
        } 
        };
        """

        cypher_query_relevant_events = """
            WITH $query_embedding AS query_vector, datetime($current_timestamp) AS query_time
            CALL db.index.vector.queryNodes('event_embedding_index', 5, query_vector) 
            YIELD node AS e, score AS event_similarity

            MATCH (u:User {client_identifier: $client_identifier})-[:PARTICIPATED_IN]->(e)
            MATCH (u)-[:HAS_ATTRIBUTE]->(pa:ProfileAttribute)
            
            WHERE event_similarity >= 0.8  // Only keep matches above 80%

            WITH e, pa, event_similarity,
                pa.confidence * exp(-pa.lambda * (duration.between(datetime(e.last_updated), query_time).seconds)) AS decayed_confidence,
                e.relevance_score * exp(-0.01 * (duration.between(datetime(e.timestamp), query_time).seconds)) AS decayed_relevance

            ORDER BY (decayed_relevance + event_similarity) DESC, decayed_confidence DESC
            LIMIT 10
            RETURN e.name AS event, e.description AS event_description, 
                decayed_relevance AS event_score, event_similarity AS similarity_score,
                pa.key AS attribute, pa.value AS attribute_value, decayed_confidence AS attribute_score;
        """

        cypher_query_relevant_profile_attributes = """
            WITH $query_embedding AS query_vector, datetime($current_timestamp) AS query_time
            CALL db.index.vector.queryNodes('profile_attribute_embedding_index', 5, query_vector) 
            YIELD node AS pa, score AS attribute_similarity

            MATCH (u:User {client_identifier: $client_identifier})-[:HAS_ATTRIBUTE]->(pa)

            WHERE attribute_similarity >= 0.8  // Only keep matches above 80%

            WITH pa, attribute_similarity,
                pa.confidence * exp(-pa.lambda * (duration.between(datetime(pa.last_updated), query_time).seconds)) AS decayed_confidence

            ORDER BY decayed_confidence DESC, attribute_similarity DESC
            LIMIT 10
            RETURN pa.key AS attribute, pa.value AS attribute_value, decayed_confidence AS attribute_score, attribute_similarity;
        """

        client_identifier = extra_params.get("client_identifier", None)

        if not query or not client_identifier:
            return {"error": "Missing required parameters: user_query or client_identifier"}
        
        from chat.utils import create_embedding
        query_embedding = create_embedding(query)
        current_timestamp = datetime.utcnow().isoformat()

        results = {"events": [], "profile_attributes": []}

        with self.driver.session() as session:
            events_result = session.run(
                cypher_query_relevant_events,
                query_embedding=query_embedding,
                client_identifier=client_identifier,
                current_timestamp=current_timestamp
            )
            results["events"] = [record.data() for record in events_result]

        with self.driver.session() as session:
            attributes_result = session.run(
                cypher_query_relevant_profile_attributes,
                query_embedding=query_embedding,
                client_identifier=client_identifier,
                current_timestamp=current_timestamp
            )
            results["profile_attributes"] = [record.data() for record in attributes_result]
        
        return results
            
    
    async def run_cypher_script(self, cypher_script: str) -> None:
        statements = [stmt.strip() for stmt in cypher_script.split(";") if stmt.strip()]
        
        results = []
        with self.driver.session() as session:
            try:
                with session.begin_transaction() as tx:
                    for stmt in statements:
                        result = tx.run(stmt)
                        results.extend(result.data())
                        print(f"✅ Executed:\n{stmt}\n")
                    tx.commit()

                print("✅ All queries committed in a single transaction!")
            except Exception as e:
                print(f"❌ Error executing queries: {e}")
        
        await self.process_and_update_embeddings(results=results)

    async def process_and_update_embeddings(self, results):
        """
        Process nodes returned from the LLM-created queries and update each with an embedding.
        
        :param results: List of dicts containing nodeId and nodeType, e.g.,
        [{'nodeId': 123, 'nodeType': 'Event'}, {'nodeId': 456, 'nodeType': 'ProfileAttribute'}]
        """
        for record in results:
            node_id = record.get('nodeId')
            node_type = record.get('nodeType')

            text_for_embedding = None

            if node_type == 'Event':
                # Query the Event node to fetch name and description
                event_query = """
                MATCH (e:Event)
                WHERE id(e) = $nodeId
                RETURN e.name AS name, e.description AS description
                """
                event_data = await self.run_cypher_query(event_query, params={'nodeId': node_id})
                if event_data and len(event_data) > 0:
                    name = event_data[0].get('name', '')
                    description = event_data[0].get('description', '')
                    text_for_embedding = f"{name} {description}".strip()
                else:
                    print(f"❌  Event node with id {node_id} not found or missing properties.")

            elif node_type == 'ProfileAttribute':
                # Query the ProfileAttribute node to fetch key and value
                pa_query = """
                MATCH (pa:ProfileAttribute)
                WHERE id(pa) = $nodeId
                RETURN pa.key AS key, pa.value AS value
                """
                pa_data = await self.run_cypher_query(pa_query, params={'nodeId': node_id})
                if pa_data and len(pa_data) > 0:
                    key = pa_data[0].get('key', '')
                    value = pa_data[0].get('value', '')
                    text_for_embedding = f"{key} {value}".strip()
                else:
                    print(f"❌  ProfileAttribute node with id {node_id} not found or missing properties.")

            else:
                print(f"❌  Unknown node type: {node_type} for node id {node_id}. Skipping.")
                continue

            if text_for_embedding:
                try:
                    from chat.utils import create_embedding
                    embedding = await sync_to_async(create_embedding)(text_for_embedding)
                except Exception as e:
                    print(f"❌ Error generating embedding for node id {node_id}: {e}")
                    continue

                update_query = """
                MATCH (n)
                WHERE id(n) = $nodeId
                SET n.embedding = $embedding
                """
                params = {'nodeId': node_id, 'embedding': embedding}
                try:
                    await self.run_cypher_query(update_query, params)
                    print(f"✅ Updated node id {node_id} ({node_type}) with embedding.")
                except Exception as e:
                    print(f"❌ Failed to update node id {node_id}: {e}")
            else:
                print(f"❌  No valid text found for node id {node_id} ({node_type}); skipping embedding update.")

    async def run_cypher_query(self, query: str, params: dict = None) -> list:
        """
        Execute a Cypher query and return the fetched results.
        """
        results = []
        with self.driver.session() as session:
            try:
                with session.begin_transaction() as tx:
                    result = tx.run(query, **(params or {}))
                    results = result.data()
                    tx.commit()
                
                self.push_knowledge_retriever_data_to_openmeter()
            except Exception as e:
                print(f"❌ Error executing query: {e}")
        return results


