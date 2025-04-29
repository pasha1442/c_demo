from neo4j import GraphDatabase
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import PromptTemplate
import re
import json
from datetime import datetime
from chat.assistants import get_active_prompt_from_langfuse
from chat.retriever.base_retriever import BaseRetriever
from basics.custom_exception import Neo4jConnectionError, Neo4jDataRetrievalError


class Neo4jJsonEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Neo4j types"""
    def default(self, obj):
        # Handle Neo4j DateTime objects
        if hasattr(obj, 'iso_format'):  # Neo4j DateTime objects have this method
            return obj.iso_format()
        # Handle other Neo4j spatial types if needed
        if hasattr(obj, 'x') and hasattr(obj, 'y'):  # Point type
            return {"x": obj.x, "y": obj.y, "z": getattr(obj, 'z', None)}
        # Handle Python datetime objects
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle bytes
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        # Handle sets
        if isinstance(obj, set):
            return list(obj)
        # Let the base class handle other types or raise TypeError
        return super().default(obj)


class Neo4jGraphDataRetriever(BaseRetriever):
    """
    Retriever for Neo4j graph data that can generate Cypher queries from natural language questions
    and return the results in a format suitable for network graph visualization.
    """

    def __init__(self, data_source=None, state=None, company=None, credentials=None):
        """
        Initialize the Neo4j Graph Data Retriever
        
        Args:
            data_source: The data source identifier
            state: The current state (optional)
            company: The company object (optional)
            credentials: Neo4j credentials dictionary (optional)
        """
        try:
            super().__init__()
            self.database = self.DATABASE_NEO4J
            self.database_type = self.DATABASE_TYPE_GRAPH_DB
            
            self.company = company
            self.session_id = None
            
            # If credentials are provided directly, use them
            if credentials:
                self.credentials_dict = credentials
            # Otherwise try to get them from company settings
            else:
                raise ValueError("Neo4j credentials must be provided")
            
            self.neo4j_username = self.credentials_dict.get("neo4j_username")
            self.neo4j_password = self.credentials_dict.get("neo4j_password")
            self.neo4j_url = self.credentials_dict.get("neo4j_url")
            
            # Initialize Neo4j driver
            self.driver = GraphDatabase.driver(
                self.neo4j_url, 
                auth=(self.neo4j_username, self.neo4j_password),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=60,
                connection_timeout=30
            )
            
            # Set up default prompt template for Cypher generation
            self.default_cypher_generation_prompt = """
            You are a Neo4j Cypher query generator. Given a database schema and a question, 
            generate a Cypher query that will answer the question.
            
            {schema}
            
            User Question: {question}
            
            Generate a Cypher query that will answer this question. The query should:
            1. Be syntactically correct Neo4j Cypher
            2. Return data in a format suitable for network graph visualization
            3. Include node labels, properties, and relationship types
            4. Limit results to 100 nodes maximum to avoid overwhelming the visualization
            5. Only use node labels, properties, and relationships that exist in the schema
            6. value of a filter will always be string in double quotes.
            
            Return ONLY the Cypher query without any explanation or markdown formatting.
            """
            
            # Try to get a custom prompt from langfuse if company is provided
            if company:
                try:
                    prompt_info = get_active_prompt_from_langfuse(company.id, "neo4j_network_graph_cypher_generation")
                    if prompt_info and "system_prompt" in prompt_info:
                        self.cypher_generation_prompt = prompt_info["system_prompt"]
                    else:
                        self.cypher_generation_prompt = self.default_cypher_generation_prompt
                except Exception:
                    self.cypher_generation_prompt = self.default_cypher_generation_prompt
            else:
                self.cypher_generation_prompt = self.default_cypher_generation_prompt
                
        except Exception as e:
            raise Neo4jConnectionError(f"Could not initialize Neo4j Graph Data Retriever: {str(e)}")

    def get_schema(self):
        """
        Get the Neo4j database schema using multiple fallback strategies
        
        Returns:
            dict: The database schema information
        """
        def get_schema_tx(tx):
            # Query for node properties
            node_properties_query = """
            CALL apoc.meta.data()
            YIELD label, other, elementType, type, property
            WHERE NOT type = "RELATIONSHIP" AND elementType = "node"
            WITH label AS nodeLabels, collect(property) AS properties
            RETURN {labels: nodeLabels, properties: properties} AS output
            """
            
            # Query for relationship properties
            rel_properties_query = """
            CALL apoc.meta.data()
            YIELD label, other, elementType, type, property
            WHERE NOT type = "RELATIONSHIP" AND elementType = "relationship"
            WITH label AS nodeLabels, collect(property) AS properties
            RETURN {type: nodeLabels, properties: properties} AS output
            """
            
            # Query for relationships between nodes
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
            
            # Alternative simpler query if the above doesn't work
            simple_schema_query = """
            CALL db.schema.visualization()
            YIELD nodes, relationships
            RETURN nodes, relationships
            """
            
            # Try the more detailed approach first
            try:
                node_props_result = tx.run(node_properties_query)
                node_props = [record["output"] for record in node_props_result]
                
                rel_props_result = tx.run(rel_properties_query)
                rel_props = [record["output"] for record in rel_props_result]
                
                rels_result = tx.run(rel_query)
                rels = [{"source": record["schemaInfo"]["source"], 
                         "relationship": record["schemaInfo"]["relationship"], 
                         "target": record["schemaInfo"]["target"],
                         "frequency": record["frequency"]} for record in rels_result]
                
                return {
                    "node_props": node_props,
                    "rel_props": rel_props,
                    "rels": rels
                }
            except Exception as e:
                print(f"Error with detailed schema query: {str(e)}")
                # Fall back to simpler schema query
                try:
                    result = tx.run(simple_schema_query)
                    record = result.single()
                    if record:
                        return {
                            "nodes": record["nodes"],
                            "relationships": record["relationships"]
                        }
                except Exception as e2:
                    print(f"Error with simple schema query: {str(e2)}")
                    
                # Last resort - try a very basic query
                try:
                    # Get node labels
                    labels_result = tx.run("CALL db.labels()")
                    labels = [record["label"] for record in labels_result]
                    
                    # Get relationship types
                    rel_types_result = tx.run("CALL db.relationshipTypes()")
                    rel_types = [record["relationshipType"] for record in rel_types_result]
                    
                    # For each label, get a sample of properties
                    node_props = []
                    for label in labels:
                        try:
                            props_result = tx.run(f"MATCH (n:{label}) RETURN keys(n) as props LIMIT 1")
                            props_record = props_result.single()
                            if props_record:
                                node_props.append({
                                    "labels": label,
                                    "properties": props_record["props"]
                                })
                        except:
                            node_props.append({
                                "labels": label,
                                "properties": []
                            })
                    
                    # Get sample relationships
                    rels = []
                    for rel_type in rel_types:
                        try:
                            sample_rel_result = tx.run(f"MATCH (a)-[r:{rel_type}]->(b) RETURN labels(a) as source_labels, labels(b) as target_labels LIMIT 1")
                            sample_rel = sample_rel_result.single()
                            if sample_rel:
                                rels.append({
                                    "source": sample_rel["source_labels"][0] if sample_rel["source_labels"] else "Unknown",
                                    "relationship": rel_type,
                                    "target": sample_rel["target_labels"][0] if sample_rel["target_labels"] else "Unknown"
                                })
                        except:
                            # If we can't get sample, just add the relationship type
                            rels.append({
                                "source": "Unknown",
                                "relationship": rel_type,
                                "target": "Unknown"
                            })
                    
                    return {
                        "node_props": node_props,
                        "rels": rels
                    }
                except Exception as e3:
                    print(f"Error with basic schema query: {str(e3)}")
                    return {"nodes": [], "relationships": []}
        
        try:
            with self.driver.session() as session:
                return session.read_transaction(get_schema_tx)
        except Exception as e:
            raise Neo4jDataRetrievalError(f"Failed to retrieve Neo4j schema: {str(e)}")

    def format_schema_text(self, graph_schema):
        """
        Format the graph schema into a text representation for the LLM prompt
        
        Args:
            graph_schema (dict): The graph schema information
            
        Returns:
            str: Formatted schema text
        """
        schema_text = "Database Schema:\n"
        
        # Format node properties
        schema_text += "Node Labels and Properties:\n"
        if "node_props" in graph_schema:
            for node in graph_schema["node_props"]:
                label = node.get("labels", "")
                properties = node.get("properties", [])
                schema_text += f"- {label}: {', '.join(properties)}\n"
        elif "nodes" in graph_schema:
            for node in graph_schema["nodes"]:
                if hasattr(node, "labels"):
                    labels = list(node.labels)
                    properties = [prop for prop in dir(node) if not prop.startswith('_') and not callable(getattr(node, prop))]
                    schema_text += f"- {', '.join(labels)}: {', '.join(properties)}\n"
        
        # Format relationships
        schema_text += "\nRelationships:\n"
        if "rels" in graph_schema:
            for rel in graph_schema["rels"]:
                source = rel.get("source", "Unknown")
                relationship = rel.get("relationship", "Unknown")
                target = rel.get("target", "Unknown")
                schema_text += f"- ({source})-[:{relationship}]->({target})\n"
        elif "relationships" in graph_schema:
            for rel in graph_schema["relationships"]:
                if hasattr(rel, "type"):
                    rel_type = rel.type
                    start_node_labels = list(rel.start_node.labels) if hasattr(rel.start_node, "labels") else ["Unknown"]
                    end_node_labels = list(rel.end_node.labels) if hasattr(rel.end_node, "labels") else ["Unknown"]
                    schema_text += f"- ({start_node_labels[0]})-[:{rel_type}]->({end_node_labels[0]})\n"
        
        # Add relationship properties if available
        if "rel_props" in graph_schema:
            schema_text += "\nRelationship Properties:\n"
            for rel_prop in graph_schema["rel_props"]:
                rel_type = rel_prop.get("type", "")
                properties = rel_prop.get("properties", [])
                schema_text += f"- {rel_type}: {', '.join(properties)}\n"
        
        return schema_text

    def generate_cypher_query(self, question):
        """
        Generate a Cypher query from a natural language question
        
        Args:
            question (str): The user's natural language question
            
        Returns:
            str: The generated Cypher query
        """
        try:
            # Get the database schema
            graph_schema = self.get_schema()
            
            # Format the schema for the prompt
            schema_text = self.format_schema_text(graph_schema)
            
            # Create the prompt template
            prompt = PromptTemplate(
                input_variables=["schema", "question"], 
                template=self.cypher_generation_prompt
            )
            
            # Generate the Cypher query using ChatGPT
            llm = ChatOpenAI(temperature=0, model="gpt-4o")
            cypher_query_chain = prompt | llm
            
            # Generate the Cypher query
            response = cypher_query_chain.invoke({
                "schema": schema_text,
                "question": question
            })
            
            # Extract the Cypher query from the response
            cypher_query = self.extract_cypher(response.content)
            
            return cypher_query
        except Exception as e:
            raise Neo4jDataRetrievalError(f"Failed to generate Cypher query: {str(e)}")

    def extract_cypher(self, text):
        """
        Extract a Cypher query from text, handling markdown formatting
        
        Args:
            text (str): The text containing a Cypher query
            
        Returns:
            str: The extracted Cypher query
        """
        # Remove any "cypher" text
        text = text.replace("cypher", "")
        
        # Try to extract code from triple backticks
        pattern = r"```(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        # Extract the first match if available
        if matches:
            return matches[0].strip()
        
        # Otherwise return the content directly
        return text.strip()

    def execute_cypher_query(self, cypher_query):
        """
        Execute a Cypher query and return the raw records
        
        Args:
            cypher_query (str): The Cypher query to execute
            
        Returns:
            list: The query results as records
        """
        def get_data(tx):
            result = tx.run(cypher_query)
            records = []
            for record in result:
                records.append(record)
            return records

        try:
            with self.driver.session() as session:
                return session.read_transaction(get_data)
        except Exception as e:
            raise Neo4jDataRetrievalError(f"Failed to execute Cypher query: {str(e)}")

    def convert_to_serializable(self, value):
        """
        Convert Neo4j values to JSON serializable values
        
        Args:
            value: The value to convert
            
        Returns:
            The converted value
        """
        if hasattr(value, 'iso_format'):  # Neo4j DateTime
            return value.iso_format()
        elif isinstance(value, datetime):  # Python datetime
            return value.isoformat()
        elif isinstance(value, bytes):  # Bytes
            return value.decode('utf-8', errors='replace')
        elif isinstance(value, set):  # Set
            return list(value)
        elif isinstance(value, (list, dict)):  # Nested structures
            try:
                # Test if serializable
                json.dumps(value, cls=Neo4jJsonEncoder)
                return value
            except (TypeError, OverflowError):
                # Convert to string if not serializable
                return str(value)
        else:
            return value

    def process_records(self, records):
        """
        Process Neo4j records into nodes and links for graph visualization
        
        Args:
            records (list): The Neo4j records
            
        Returns:
            dict: Dictionary with nodes and links
        """
        nodes = []
        links = []
        node_map = {}  # To track nodes we've already processed
        
        # Process the records to extract nodes and relationships
        for record in records:
            # Check for different types of Neo4j objects
            for key, value in record.items():
                # Check if it's a Path object with nodes and relationships collections
                if hasattr(value, 'nodes') and hasattr(value, 'relationships'):
                    path = value
                    
                    # Extract all nodes from the path
                    for node in path.nodes:
                        node_id = str(node.element_id)
                        if node_id not in node_map:
                            node_data = {
                                "id": node_id,
                                "labels": list(node.labels),
                                "group": 1  # Default group
                            }
                            
                            # Add node properties
                            for prop_key, prop_value in node.items():
                                if prop_key not in node_data and prop_value is not None:
                                    # Convert non-serializable types
                                    node_data[prop_key] = self.convert_to_serializable(prop_value)
                            
                            nodes.append(node_data)
                            node_map[node_id] = len(nodes) - 1
                    
                    # Extract all relationships from the path
                    for rel in path.relationships:
                        source_id = str(rel.start_node.element_id)
                        target_id = str(rel.end_node.element_id)
                        
                        link = {
                            "source": source_id,
                            "target": target_id,
                            "type": rel.type,
                            "relationship": rel.type,  # For compatibility
                            "value": 1  # Default value
                        }
                        
                        # Add relationship properties
                        for prop_key, prop_value in rel.items():
                            if prop_key not in link and prop_value is not None:
                                # Convert non-serializable types
                                link[prop_key] = self.convert_to_serializable(prop_value)
                        
                        links.append(link)
                
                # Check if it's a Relationship object with type and start/end nodes
                elif hasattr(value, 'type') and hasattr(value, 'start_node') and hasattr(value, 'end_node'):
                    rel = value
                    source_id = str(rel.start_node.element_id)
                    target_id = str(rel.end_node.element_id)
                    
                    # Make sure both nodes are in our node list
                    if source_id not in node_map:
                        source_node = {
                            "id": source_id,
                            "labels": list(rel.start_node.labels),
                            "group": 1  # Default group
                        }
                        
                        # Add node properties
                        for prop_key, prop_value in rel.start_node.items():
                            if prop_key not in source_node and prop_value is not None:
                                # Convert non-serializable types
                                source_node[prop_key] = self.convert_to_serializable(prop_value)
                        
                        nodes.append(source_node)
                        node_map[source_id] = len(nodes) - 1
                    
                    if target_id not in node_map:
                        target_node = {
                            "id": target_id,
                            "labels": list(rel.end_node.labels),
                            "group": 1  # Default group
                        }
                        
                        # Add node properties
                        for prop_key, prop_value in rel.end_node.items():
                            if prop_key not in target_node and prop_value is not None:
                                # Convert non-serializable types
                                target_node[prop_key] = self.convert_to_serializable(prop_value)
                        
                        nodes.append(target_node)
                        node_map[target_id] = len(nodes) - 1
                    
                    link = {
                        "source": source_id,
                        "target": target_id,
                        "type": rel.type,
                        "relationship": rel.type,  # For compatibility
                        "value": 1  # Default value
                    }
                    
                    # Add relationship properties
                    for prop_key, prop_value in rel.items():
                        if prop_key not in link and prop_value is not None:
                            # Convert non-serializable types
                            link[prop_key] = self.convert_to_serializable(prop_value)
                    
                    links.append(link)
                
                # Check if it's a Node object
                elif hasattr(value, 'element_id') and hasattr(value, 'labels'):
                    node = value
                    node_id = str(node.element_id)
                    
                    if node_id not in node_map:
                        node_data = {
                            "id": node_id,
                            "labels": list(node.labels),
                            "group": 1  # Default group
                        }
                        
                        # Add node properties
                        for prop_key, prop_value in node.items():
                            if prop_key not in node_data and prop_value is not None:
                                # Convert non-serializable types
                                node_data[prop_key] = self.convert_to_serializable(prop_value)
                        
                        nodes.append(node_data)
                        node_map[node_id] = len(nodes) - 1
        
        # Assign colors based on node labels
        self.assign_colors_to_nodes(nodes)
        
        return {
            "nodes": nodes,
            "links": links
        }

    def assign_colors_to_nodes(self, nodes):
        """
        Assign colors to nodes based on their labels
        
        Args:
            nodes (list): The list of nodes to assign colors to
        """
        # Define a color palette similar to Neo4j Browser
        color_palette = [
            "#68BDF6",  # light blue
            "#6DCE9E",  # green
            "#FF756E",  # salmon
            "#DE9BF9",  # purple
            "#FB95AF",  # pink
            "#FFD86E",  # yellow
            "#A5ABB6",  # gray
            "#9CC4E4",  # steel blue
            "#C2FABC",  # mint
            "#FFA3A3",  # light red
            "#D9C8AE",  # tan
            "#B3B3FF",  # lavender
            "#FF9CEE",  # light pink
            "#EAACFF"   # light purple
        ]
        
        # Collect all unique labels
        label_colors = {}
        all_labels = set()
        for node in nodes:
            for label in node.get("labels", []):
                all_labels.add(label)
        
        # Assign colors to labels
        for i, label in enumerate(sorted(all_labels)):
            label_colors[label] = color_palette[i % len(color_palette)]
        
        # Add color to each node based on its first label
        for node in nodes:
            if node.get("labels"):
                primary_label = node["labels"][0]
                node["color"] = label_colors.get(primary_label, "#A5ABB6")  # Default to gray if label not found

    def query(self, question):
        """
        Process a natural language question and return graph data
        
        Args:
            question (str): The user's natural language question
            
        Returns:
            dict: The graph data with nodes and links
        """
        try:
            # Generate Cypher query from the question
            cypher_query = self.generate_cypher_query(question)
            
            # Execute the query
            records = self.execute_cypher_query(cypher_query)
            
            # Process the records into graph data
            graph_data = self.process_records(records)
            
            # Add the original question and generated query to the result
            result = {
                "original_question": question,
                "generated_query": cypher_query,
                "nodes": graph_data["nodes"],
                "links": graph_data["links"]
            }
            
            return result
        except Exception as e:
            raise Neo4jDataRetrievalError(f"Failed to process question: {str(e)}")
    
    def close(self):
        """Close the Neo4j driver connection"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
