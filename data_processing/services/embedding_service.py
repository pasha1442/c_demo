"""Service for handling data embeddings operations with Neo4j"""
import json
import os
import time
import uuid
import traceback
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

import openai
from neo4j import GraphDatabase
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
import concurrent.futures

from backend.logger import Logger
from company.utils import CompanyUtils
from company.models import CompanySetting
from data_processing.models import DataEmbedding

from backend.settings.base import SENTRY_DSN_URL


BATCH_SIZE_DEFAULT = 50
MAX_LABEL_WORKERS_DEFAULT = 3
MAX_BATCH_WORKERS_DEFAULT = 3

logger = Logger(Logger.INFO_LOG)

class EmbeddingTimer:
    """A utility class to track timing metrics for embedding generation"""
    def __init__(self):
        self.total_nodes_processed = 0
        self.total_embeddings_generated = 0
        self.total_processing_time = 0
        self.label_processing_times = {}
        self.batch_processing_times = {}
        self.embedding_group_times = {}
        self.start_time = None

    def start(self):
        """Start the overall timer"""
        self.start_time = time.time()
        return self.start_time

    def stop(self):
        """Stop the overall timer and calculate total processing time"""
        if self.start_time:
            self.total_processing_time = time.time() - self.start_time
            return self.total_processing_time

    def start_label_timer(self, label):
        """Start timer for a specific label"""
        timer_id = f"label_{label}_{uuid.uuid4()}"
        self.label_processing_times[timer_id] = {"label": label, "start": time.time(), "end": None}
        return timer_id

    def stop_label_timer(self, timer_id):
        """Stop timer for a specific label"""
        if timer_id in self.label_processing_times:
            self.label_processing_times[timer_id]["end"] = time.time()
            duration = self.label_processing_times[timer_id]["end"] - self.label_processing_times[timer_id]["start"]
            return duration
        return None

    def start_batch_timer(self, label, batch_num):
        """Start timer for a specific batch"""
        timer_id = f"batch_{label}_{batch_num}_{uuid.uuid4()}"
        self.batch_processing_times[timer_id] = {
            "label": label, 
            "batch_num": batch_num, 
            "start": time.time(), 
            "end": None
        }
        return timer_id

    def stop_batch_timer(self, timer_id):
        """Stop timer for a specific batch"""
        if timer_id in self.batch_processing_times:
            self.batch_processing_times[timer_id]["end"] = time.time()
            duration = self.batch_processing_times[timer_id]["end"] - self.batch_processing_times[timer_id]["start"]
            return duration
        return None
        
    def start_group_timer(self, label, group_name):
        """Start timer for a specific embedding group"""
        timer_id = f"group_{label}_{group_name}_{uuid.uuid4()}"
        self.embedding_group_times[timer_id] = {
            "label": label,
            "group_name": group_name,
            "start": time.time(),
            "end": None
        }
        return timer_id
        
    def stop_group_timer(self, timer_id):
        """Stop timer for a specific embedding group"""
        if timer_id in self.embedding_group_times:
            self.embedding_group_times[timer_id]["end"] = time.time()
            duration = self.embedding_group_times[timer_id]["end"] - self.embedding_group_times[timer_id]["start"]
            return duration
        return None

    def increment_nodes_processed(self, count=1):
        """Increment the count of processed nodes"""
        self.total_nodes_processed += count

    def increment_embeddings_generated(self, count=1):
        """Increment the count of generated embeddings"""
        self.total_embeddings_generated += count

    def get_summary(self):
        """Generate a summary of timing metrics"""
        label_durations = {}
        for timer_data in self.label_processing_times.values():
            if timer_data["end"]:
                label = timer_data["label"]
                duration = timer_data["end"] - timer_data["start"]
                if label not in label_durations:
                    label_durations[label] = []
                label_durations[label].append(duration)
        
        avg_label_times = {
            label: sum(durations) / len(durations) 
            for label, durations in label_durations.items()
        }
        
        # Calculate average processing time per batch
        batch_durations = {}
        for timer_data in self.batch_processing_times.values():
            if timer_data["end"]:
                label = timer_data["label"]
                if label not in batch_durations:
                    batch_durations[label] = []
                batch_durations[label].append(timer_data["end"] - timer_data["start"])
        
        avg_batch_times = {
            label: sum(durations) / len(durations) 
            for label, durations in batch_durations.items()
        }
        
        # Calculate embedding group stats
        group_stats = {}
        for timer_data in self.embedding_group_times.values():
            if timer_data["end"]:
                label = timer_data["label"]
                group_name = timer_data["group_name"]
                duration = timer_data["end"] - timer_data["start"]
                
                if label not in group_stats:
                    group_stats[label] = {}
                
                if group_name not in group_stats[label]:
                    group_stats[label][group_name] = {
                        "times": [],
                        "count": 0
                    }
                
                group_stats[label][group_name]["times"].append(duration)
                group_stats[label][group_name]["count"] += 1
        
        # Calculate averages for each group
        embedding_group_stats = {}
        for label, groups in group_stats.items():
            embedding_group_stats[label] = {}
            for group_name, data in groups.items():
                avg_time = sum(data["times"]) / len(data["times"]) if data["times"] else 0
                embedding_group_stats[label][group_name] = {
                    "count": data["count"],
                    "avg_time": avg_time
                }
        
        return {
            "total_nodes_processed": self.total_nodes_processed,
            "total_embeddings_generated": self.total_embeddings_generated,
            "total_processing_time": self.total_processing_time,
            "average_label_processing_times": avg_label_times,
            "average_batch_processing_times": avg_batch_times,
            "embedding_group_stats": embedding_group_stats
        }


class Neo4jEmbedding:
    def __init__(self, uri, user, password, timer=None):
        self.driver = GraphDatabase.driver(
            uri, 
            auth=(user, password),
            max_connection_lifetime=3600,
            connection_acquisition_timeout=60,
            connection_timeout=30
        )
        self.timer = timer or EmbeddingTimer()
        
    def close(self):
        """Close the database connection."""
        self.driver.close()

    def verify_connection(self):
        """Verify Neo4j connection"""
        try:
            self.driver.verify_connectivity()
            return True, "Neo4j connection successful"
        except Exception as e:
            error_msg = f"Neo4j connection failed: {str(e)}"
            logger.add(error_msg)
            return False, error_msg

    def get_all_labels(self):
        """Fetch all labels from Neo4j."""
        query = "CALL db.labels()"
        
        with self.driver.session() as session:
            print(f"🔍 Fetching all labels from Neo4j...")
            result = session.run(query)
            labels = [record[0] for record in result]
            print(f"✅ Found {len(labels)} labels: {', '.join(labels)}")
            return labels

    def get_nodes_for_label(self, label):
        """Fetch all nodes for a given label and their properties."""
        query = f"MATCH (n:`{label}`) RETURN elementId(n) as id, properties(n) as props"
        
        with self.driver.session() as session:
            print(f"🔍 Fetching nodes with label '{label}'...")
            result = session.run(query)
            nodes = [{"id": record["id"], "props": record["props"]} for record in result]
            print(f"✅ Found {len(nodes)} nodes with label '{label}'")
            return nodes

    def initialize_node_embedding_properties(self, node_id, embedding_group_name=None):
        """Initialize embedding-related properties for a specific node and embedding group."""
        if not node_id:
            return

        if not embedding_group_name:
            query = """
            MATCH (n) WHERE elementId(n) = $node_id 
            SET n.embedding = [],
                n.is_valid_embedding = False
            """
            
            with self.driver.session() as session:
                print(f"🔧 Initializing default embedding properties for node {node_id}...")
                session.run(query, node_id=node_id)
                print(f"✅ Initialized default embedding properties for node {node_id}")
        else:
            query = """
            MATCH (n) WHERE elementId(n) = $node_id 
            SET n[$group_name] = [],
                n[$valid_flag] = False
            """
            
            with self.driver.session() as session:
                print(f"🔧 Initializing {embedding_group_name} embedding properties for node {node_id}...")
                session.run(
                    query, 
                    node_id=node_id,
                    group_name=embedding_group_name,
                    valid_flag=f"{embedding_group_name}_is_valid"
                )
                print(f"✅ Initialized {embedding_group_name} embedding properties for node {node_id}")

    def batch_initialize_node_properties(self, node_ids, embedding_group_name=None):
        """Initialize embedding-related properties for multiple nodes."""
        if not node_ids:
            return

        if not embedding_group_name:
            query = """
            UNWIND $node_ids AS node_id
            MATCH (n) WHERE elementId(n) = node_id 
            SET n.embedding = [],
                n.is_valid_embedding = False
            """
            
            with self.driver.session() as session:
                print(f"🔧 Initializing default embedding properties for {len(node_ids)} nodes...")
                session.run(query, node_ids=node_ids)
                print(f"✅ Initialized default embedding properties for {len(node_ids)} nodes")
        else:
            query = """
            UNWIND $node_ids AS node_id
            MATCH (n) WHERE elementId(n) = node_id 
            SET n[$group_name] = [],
                n[$valid_flag] = False
            """
            
            with self.driver.session() as session:
                print(f"🔧 Initializing {embedding_group_name} embedding properties for {len(node_ids)} nodes...")
                session.run(
                    query, 
                    node_ids=node_ids,
                    group_name=embedding_group_name,
                    valid_flag=f"{embedding_group_name}_is_valid"
                )
                print(f"✅ Initialized {embedding_group_name} embedding properties for {len(node_ids)} nodes")

    def update_embedding(self, node_id, embedding, embedding_group_name=None):
        """Update embedding for a specific node and embedding group."""
        if embedding is None:
            return False
            
        # if embedding:
            # embedding_json = json.dumps(embedding)
        
        if not embedding_group_name:
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            SET n.embedding = $embedding,
                n.is_valid_embedding = True
            """
            
            with self.driver.session() as session:
                print(f"💾 Updating default embedding for node {node_id}...")
                session.run(
                    query,
                    node_id=node_id,
                    embedding=embedding
                )
                print(f"✅ Updated default embedding for node {node_id}")
        else:
            query = """
            MATCH (n) WHERE elementId(n) = $node_id
            SET n[$group_name] = $embedding,
                n[$valid_flag] = True
            """
            
            with self.driver.session() as session:
                print(f"💾 Updating {embedding_group_name} embedding for node {node_id}...")
                session.run(
                    query,
                    node_id=node_id,
                    group_name=embedding_group_name,
                    embedding=embedding,
                    valid_flag=f"{embedding_group_name}_is_valid"
                )
                print(f"✅ Updated {embedding_group_name} embedding for node {node_id}")
                
        return True

    def batch_update_embeddings(self, embedding_data):
        """Update embeddings for multiple nodes in a single batch operation.
        
        embedding_data should be a list of dictionaries, each containing:
            - node_id: The ID of the node to update
            - embedding: The embedding vector
            - group_name: (Optional) The name of the embedding group
        """
        if not embedding_data:
            return 0
        
        default_embeddings = []
        group_embeddings = {}
        
        for item in embedding_data:
            node_id = item['node_id']
            embedding = item['embedding']
            group_name = item.get('group_name')
            
            if not embedding:
                continue
                
            # embedding_str = json.dumps(embedding)
            
            if not group_name:
                default_embeddings.append({
                    'node_id': node_id,
                    'embedding': embedding
                })
            else:
                if group_name not in group_embeddings:
                    group_embeddings[group_name] = []
                    
                group_embeddings[group_name].append({
                    'node_id': node_id,
                    'embedding': embedding
                })
        
        total_updates = 0
        
        if default_embeddings:
            query = """
            UNWIND $batch AS item
            MATCH (n) WHERE elementId(n) = item.node_id
            SET n.embedding = item.embedding,
                n.is_valid_embedding = True
            """
            
            with self.driver.session() as session:
                print(f"💾 Updating default embeddings for {len(default_embeddings)} nodes in batch...")
                session.run(query, batch=default_embeddings)
                print(f"✅ Updated default embeddings for {len(default_embeddings)} nodes")
                total_updates += len(default_embeddings)
        
        for group_name, group_batch in group_embeddings.items():
            query = """
            UNWIND $batch AS item
            MATCH (n) WHERE elementId(n) = item.node_id
            SET n[$group_name] = item.embedding,
                n[$valid_flag] = True
            """
            
            with self.driver.session() as session:
                print(f"💾 Updating {group_name} embeddings for {len(group_batch)} nodes in batch...")
                session.run(
                    query, 
                    batch=group_batch,
                    group_name=group_name,
                    valid_flag=f"{group_name}_is_valid"
                )
                print(f"✅ Updated {group_name} embeddings for {len(group_batch)} nodes")
                total_updates += len(group_batch)
                
        return total_updates

    def filter_nodes_for_embedding(self, nodes, embedding_group_name=None):
        """Filter nodes that need embedding processing."""
        nodes_to_initialize = []
        nodes_to_process = []
        
        for node in nodes:
            node_id = node["id"]
            props = node["props"]
            
            if not embedding_group_name:
                if 'embedding' not in props or 'is_valid_embedding' not in props:
                    nodes_to_initialize.append(node_id)
                    nodes_to_process.append(node)
                elif props['is_valid_embedding'] == False:
                    nodes_to_initialize.append(node_id)
                    nodes_to_process.append(node)
            else:
                valid_flag = f"{embedding_group_name}_is_valid"
                if embedding_group_name not in props or valid_flag not in props:
                    nodes_to_initialize.append(node_id)
                    nodes_to_process.append(node)
                elif props[valid_flag] == False:
                    nodes_to_initialize.append(node_id)
                    nodes_to_process.append(node)
                
        return nodes_to_initialize, nodes_to_process


class DataEmbeddingService:
    def __init__(self, api_key, embedding_job=None):
        openai.api_key = api_key
        self.embedding_job = embedding_job
        self.timer = EmbeddingTimer()
        self.neo4j_client = None
        self.company = None
        self.status_metadata = {}
        
        if embedding_job:
            self.company = embedding_job.company
            self.batch_size = embedding_job.batch_size or BATCH_SIZE_DEFAULT
            self.max_label_workers = embedding_job.max_label_workers or MAX_LABEL_WORKERS_DEFAULT
            self.max_batch_workers = embedding_job.max_batch_workers or MAX_BATCH_WORKERS_DEFAULT
            
            if hasattr(embedding_job, 'status_metadata') and embedding_job.status_metadata:
                if isinstance(embedding_job.status_metadata, dict):
                    self.status_metadata = embedding_job.status_metadata
                elif isinstance(embedding_job.status_metadata, str):
                    try:
                        self.status_metadata = json.loads(embedding_job.status_metadata)
                    except json.JSONDecodeError:
                        self.status_metadata = {}
        else:
            self.batch_size = BATCH_SIZE_DEFAULT
            self.max_label_workers = MAX_LABEL_WORKERS_DEFAULT
            self.max_batch_workers = MAX_BATCH_WORKERS_DEFAULT

    def generate_embedding(self, data):
        """
        Generate vector embedding for any type of data by converting to string.
        Handles different data types gracefully.
        """
        try:
            text_data = str(data)
            
            response = openai.embeddings.create(
                model="text-embedding-ada-002",
                input=text_data
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Error generating embedding: {e}")
            logger.add(f"Error generating embedding: {e}")
            return None
            
    def generate_embeddings_batch(self, texts):
        """
        Generate embeddings for a batch of texts in a single API call.
        Returns a list of embeddings in the same order as the input texts.
        """
        if not texts:
            return []
            
        try:
            print(f"🔄 Generating embeddings for {len(texts)} texts...")
            response = openai.embeddings.create(
                model="text-embedding-ada-002",
                input=texts
            )
            
            sorted_embeddings = []
            for i in range(len(texts)):
                for data in response.data:
                    if data.index == i:
                        sorted_embeddings.append(data.embedding)
                        break
                        
            print(f"✅ Generated {len(sorted_embeddings)} embeddings")
            return sorted_embeddings
        except Exception as e:
            error_msg = f"Error generating batch embeddings: {e}"
            print(f"❌ {error_msg}")
            logger.add(error_msg)
            return [None] * len(texts)

    def _setup_neo4j_connection(self):
        try:
            credentials = CompanySetting.without_company_objects.get(
                key=CompanySetting.KEY_CHOICE_KG_NEO4J_CREDENTIALS, 
                company=self.company
            )
            credentials_dict = {k: v for d in credentials.value for k, v in d.items()}
            
            neo4j_username = credentials_dict.get("neo4j_username")
            neo4j_password = credentials_dict.get("neo4j_password")
            neo4j_url = credentials_dict.get("neo4j_url")
                
            self.neo4j_client = Neo4jEmbedding(neo4j_url, neo4j_username, neo4j_password, self.timer)
            
            connection_status, message = self.neo4j_client.verify_connection()
            if not connection_status:
                raise ValueError(message)
                
            print("\n==== NEO4J CONNECTION SUCCESSFUL ====\n")
            return True, "Neo4j connection successful"
        
        except Exception as e:
            error_msg = f"Failed to set up Neo4j connection: {str(e)}"
            print(f"\n==== NEO4J CONNECTION FAILED: {e} ====\n")
            logger.add(error_msg)
            traceback.print_exc()
            return False, error_msg
        
    def _setup_openai_connection(self):
        """Set up OpenAI connection using credentials from environment variables"""
        try:
            openai_api_key = os.environ.get('OPENAI_API_KEY')
            
            if not openai_api_key:
                if self.embedding_job and hasattr(self.embedding_job, 'OPENAI_API_KEY') and self.embedding_job.OPENAI_API_KEY:
                    openai_api_key = self.embedding_job.OPENAI_API_KEY
                else:
                    raise ValueError("OpenAI API key not found in environment variables or job settings")
            
            openai.api_key = openai_api_key
            
            test_response = self.generate_embedding("test connection")
            if not test_response:
                raise ValueError("OpenAI connection test failed")
                
            print("\n==== OPENAI CONNECTION SUCCESSFUL ====\n")
            return True, "OpenAI connection successful"
            
        except Exception as e:
            error_msg = f"Failed to set up OpenAI connection: {str(e)}"
            print(f"\n==== OPENAI CONNECTION FAILED: {e} ====\n")
            logger.add(error_msg)
            traceback.print_exc()
            return False, error_msg

    def process_node_group_embedding(self, node, label, group_name, properties):
        """Process a single node for a specific embedding group"""
        group_timer_id = self.timer.start_group_timer(label, group_name)
        node_id = node["id"]
        props = node["props"]
        
        filtered_values = []
        for prop in properties:
            if prop in props:
                filtered_values.append(str(props[prop]))
        
        group_text = " ".join(filtered_values)
        
        if not group_text.strip():
            print(f"⚠️ No valid text for {group_name} embedding of node {node_id}")
            self.timer.stop_group_timer(group_timer_id)
            return None
        
        embedding = self.generate_embedding(group_text)
        
        if embedding:
            success = self.neo4j_client.update_embedding(node_id, embedding, group_name)
            if success:
                self.timer.increment_embeddings_generated(1)
                duration = self.timer.stop_group_timer(group_timer_id)
                print(f"✅ Generated {group_name} embedding for node {node_id} in {duration:.2f}s")
                return {
                    "node_id": node_id,
                    "group_name": group_name,
                    "embedding": embedding
                }
        
        self.timer.stop_group_timer(group_timer_id)
        return None

    def process_node_whole_embedding(self, node, label):
        """Process a node to generate a single embedding from all properties"""
        node_id = node["id"]
        props = node["props"]
        
        filtered_props = {k: v for k, v in props.items() 
                        if k not in ["is_valid_embedding", "embedding"] and not k.endswith("_is_valid")}
        
        all_properties_text = " ".join(str(value) for value in filtered_props.values())
        
        if not all_properties_text.strip():
            print(f"⚠️ No valid text for whole node embedding of node {node_id}")
            return None
        
        embedding = self.generate_embedding(all_properties_text)
        
        if embedding:
            success = self.neo4j_client.update_embedding(node_id, embedding)
            if success:
                self.timer.increment_embeddings_generated(1)
                return {
                    "node_id": node_id,
                    "embedding": embedding
                }
        
        return None

    def process_batch(self, batch, label, batch_num):
        """Process a batch of nodes to generate and update embeddings."""
        batch_timer_id = self.timer.start_batch_timer(label, batch_num)
        print(f"⏱️ Started processing batch {batch_num} for label '{label}' with {len(batch)} nodes")
        
        embedding_groups = {}
        if self.embedding_job and hasattr(self.embedding_job, 'embedding_groups'):
            if isinstance(self.embedding_job.embedding_groups, dict):
                embedding_groups = self.embedding_job.embedding_groups.get(label, {})
        
        generate_whole_node = False
        if self.embedding_job and hasattr(self.embedding_job, 'whole_nodes'):
            generate_whole_node = self.embedding_job.whole_nodes
            
        
        if not embedding_groups and not generate_whole_node:
            generate_whole_node = True
            
        all_embedding_results = []
        
        for node in batch:
            node_embeddings = []
            
            for group_name, properties in embedding_groups.items():
                result = self.process_node_group_embedding(node, label, group_name, properties)
                if result:
                    node_embeddings.append(result)
            
            if generate_whole_node:
                result = self.process_node_whole_embedding(node, label)
                if result:
                    node_embeddings.append(result)
            
            all_embedding_results.extend(node_embeddings)
        
        if all_embedding_results:
            self.neo4j_client.batch_update_embeddings(all_embedding_results)
        
        duration = self.timer.stop_batch_timer(batch_timer_id)
        print(f"⌛ Completed batch {batch_num} for label '{label}' in {duration:.2f} seconds")
        
        return {
            "label": label,
            "batch_num": batch_num,
            "nodes_processed": len(batch),
            "embeddings_generated": len(all_embedding_results)
        }

    def process_label(self, label):
        """Process all nodes for a given label in parallel batches."""
        label_timer_id = self.timer.start_label_timer(label)
        print(f"🏷️ Started processing label '{label}'")
        
        try:
            nodes = self.neo4j_client.get_nodes_for_label(label)
            
            if not nodes:
                print(f"⚠️ No nodes found for label '{label}'")
                self.timer.stop_label_timer(label_timer_id)
                return {
                    "label": label,
                    "nodes_processed": 0,
                    "batches_processed": 0
                }
            
            embedding_groups = {}
            if self.embedding_job and hasattr(self.embedding_job, 'embedding_groups'):
                if isinstance(self.embedding_job.embedding_groups, dict):
                    embedding_groups = self.embedding_job.embedding_groups.get(label, {})
            
            generate_whole_node = False
            if self.embedding_job and hasattr(self.embedding_job, 'whole_nodes'):
                generate_whole_node = self.embedding_job.whole_nodes
                
            
            if not embedding_groups and not generate_whole_node:
                generate_whole_node = True
                
            if generate_whole_node:
                nodes_to_initialize, nodes_to_process = self.neo4j_client.filter_nodes_for_embedding(nodes)
                
                if nodes_to_initialize:
                    self.neo4j_client.batch_initialize_node_properties(nodes_to_initialize)
            
            
            for group_name in embedding_groups.keys():
                nodes_to_initialize, _ = self.neo4j_client.filter_nodes_for_embedding(nodes, group_name)
                
                if nodes_to_initialize:
                    self.neo4j_client.batch_initialize_node_properties(nodes_to_initialize, group_name)
            
            batches = [nodes[i:i + self.batch_size] for i in range(0, len(nodes), self.batch_size)]
            print(f"📦 Created {len(batches)} batches for label '{label}'")
            
            batch_results = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_batch_workers) as executor:
                future_to_batch = {
                    executor.submit(
                        self.process_batch, 
                        batch, 
                        label, 
                        batch_idx
                    ): batch_idx 
                    for batch_idx, batch in enumerate(batches)
                }
                
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch_idx = future_to_batch[future]
                    try:
                        result = future.result()
                        batch_results.append(result)
                        
                        if self.embedding_job:
                            self._update_job_status()
                            
                    except Exception as e:
                        error_msg = f"Error processing batch {batch_idx} for label '{label}': {e}"
                        print(f"❌ {error_msg}")
                        logger.add(error_msg)
            
            total_nodes_processed = sum(result["nodes_processed"] for result in batch_results)
            self.timer.increment_nodes_processed(total_nodes_processed)
            
            duration = self.timer.stop_label_timer(label_timer_id)
            print(f"🏁 Completed processing label '{label}' in {duration:.2f} seconds")
            
            return {
                "label": label,
                "nodes_processed": total_nodes_processed,
                "batches_processed": len(batches)
            }
            
        except Exception as e:
            error_msg = f"Error processing label '{label}': {e}"
            print(f"❌ {error_msg}")
            logger.add(error_msg)
            traceback.print_exc()
            
            if label_timer_id:
                self.timer.stop_label_timer(label_timer_id)
                
            return {
                "label": label,
                "error": str(e),
                "nodes_processed": 0,
                "batches_processed": 0
            }

    def _update_job_status(self):
        """Update embedding job status and progress"""
        if not self.embedding_job:
            return
            
        try:
            CompanyUtils.set_company_registry(self.company)
            
            total_processed = self.timer.total_nodes_processed
            total_generated = self.timer.total_embeddings_generated
            
            summary = self.timer.get_summary()
            
            status_metadata = {
                "total_nodes_processed": total_processed,
                "total_embeddings_generated": total_generated,
                "total_processing_time": self.timer.total_processing_time,
                "average_label_processing_times": summary.get("average_label_processing_times", {}),
                "average_batch_processing_times": summary.get("average_batch_processing_times", {}),
                "embedding_group_stats": summary.get("embedding_group_stats", {}),
                "last_updated": timezone.now().isoformat()
            }
            
            completion_percentage = 0
            if self.embedding_job.nodes_processed > 0:
                completion_percentage = min(
                    int((total_processed / self.embedding_job.nodes_processed) * 100),
                    99  
                )
            elif total_processed > 0:
                completion_percentage = 50 
            
            DataEmbedding.objects.filter(id=self.embedding_job.id).update(
                nodes_processed=total_processed,
                embeddings_generated=total_generated,
                total_processing_time=self.timer.total_processing_time,
                completion_percentage=completion_percentage,
                status_metadata=status_metadata
            )
            
        except Exception as e:
            error_msg = f"Error updating job status: {e}"
            print(f"❌ {error_msg}")
            logger.add(error_msg)

    def process_embedding_job(self):
        """Process embedding job with all configured labels"""
        if not self.embedding_job:
            raise ValueError("No embedding job provided")
            
        try:
            print(f"🚀 Starting embedding job: {self.embedding_job.name}")
            
            CompanyUtils.set_company_registry(self.company)
            
            DataEmbedding.objects.filter(id=self.embedding_job.id).update(
                status=DataEmbedding.STATUS_PROCESSING,
                execution_start_at=timezone.now(),
                completion_percentage=0
            )
            
            self.timer.start()
            print(f"⏱️ Timer started at {datetime.fromtimestamp(self.timer.start_time).strftime('%Y-%m-%d %H:%M:%S')}")
            
            neo4j_status, neo4j_msg = self._setup_neo4j_connection()
            openai_status, openai_msg = self._setup_openai_connection()
            
            if not neo4j_status or not openai_status:
                error_msg = f"Connection setup failed: {neo4j_msg}, {openai_msg}"
                self._handle_error(error_msg)
                return False
            
            target_labels = self.embedding_job.labels
            
            if not target_labels or len(target_labels) == 0:
                target_labels = self.neo4j_client.get_all_labels()
                print(f"No specific labels configured, using all {len(target_labels)} labels from database")
            else:
                print(f"Processing {len(target_labels)} configured labels: {', '.join(target_labels)}")
                
            if not target_labels:
                error_msg = "No labels found to process"
                self._handle_error(error_msg)
                return False
                
            if hasattr(self.embedding_job, 'embedding_groups') and self.embedding_job.embedding_groups:
                print(f"Using embedding groups configuration:")
                for label, groups in self.embedding_job.embedding_groups.items():
                    print(f"  Label '{label}':")
                    for group_name, props in groups.items():
                        print(f"    - {group_name}: {', '.join(props)}")
            
            if hasattr(self.embedding_job, 'whole_nodes') and self.embedding_job.whole_nodes:
                print(f"Also generating embeddings for whole nodes")
                
            label_results = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_label_workers) as executor:
                future_to_label = {
                    executor.submit(
                        self.process_label, 
                        label
                    ): label 
                    for label in target_labels
                }
                
                for future in concurrent.futures.as_completed(future_to_label):
                    label = future_to_label[future]
                    try:
                        result = future.result()
                        label_results.append(result)
                        
                        # Update job status
                        self._update_job_status()
                        
                    except Exception as e:
                        error_msg = f"Error processing label '{label}': {e}"
                        print(f"❌ {error_msg}")
                        logger.add(error_msg)
                        
                        # Add error result
                        label_results.append({
                            "label": label,
                            "error": str(e),
                            "nodes_processed": 0,
                            "batches_processed": 0
                        })
            
            if self.neo4j_client:
                self.neo4j_client.close()
            
            self.timer.stop()
            processing_time = self.timer.total_processing_time
            
            CompanyUtils.set_company_registry(self.company)
            DataEmbedding.objects.filter(id=self.embedding_job.id).update(
                status=DataEmbedding.STATUS_DONE,
                execution_end_at=timezone.now(),
                completion_percentage=100,
                nodes_processed=self.timer.total_nodes_processed,
                embeddings_generated=self.timer.total_embeddings_generated,
                total_processing_time=processing_time,
                status_metadata=self.timer.get_summary()
            )
            
            print("\n🔍 --- Embedding Generation Summary ---")
            print(f"⏱️ Total processing time: {processing_time:.2f} seconds")
            print(f"📊 Total nodes processed: {self.timer.total_nodes_processed}")
            print(f"🔢 Total embeddings generated: {self.timer.total_embeddings_generated}")
            
            print("\n📋 Label Processing Results:")
            for result in label_results:
                if "error" in result:
                    print(f"  🏷️ {result['label']}: Error - {result['error']}")
                else:
                    print(f"  🏷️ {result['label']}: {result['nodes_processed']} nodes in {result['batches_processed']} batches")
            
            print("\n⏱️ Average Processing Times by Label:")
            summary = self.timer.get_summary()
            for label, avg_time in summary.get("average_label_processing_times", {}).items():
                print(f"  🏷️ {label}: {avg_time:.2f} seconds")
            
            print("\n📊 Embedding Group Statistics:")
            for label, groups in summary.get("embedding_group_stats", {}).items():
                print(f"  🏷️ {label}:")
                for group_name, stats in groups.items():
                    print(f"    - {group_name}: {stats['count']} embeddings, avg time: {stats['avg_time']:.2f}s")
            
            print("\n🎉 Embedding generation complete!")
            return True
            
        except Exception as e:
            error_msg = f"Error processing embedding job: {e}"
            self._handle_error(error_msg)
            traceback.print_exc()
            return False

    def _handle_error(self, error_msg):
        """Handle errors during embedding processing"""
        if not self.embedding_job:
            print(f"❌ Error (no job context): {error_msg}")
            logger.add(f"Error (no job context): {error_msg}")
            return
            
        try:
            print(f"❌ Error: {error_msg}")
            logger.add(error_msg)
            
            CompanyUtils.set_company_registry(self.company)
            
            if self.timer.start_time:
                self.timer.stop()
                processing_time = self.timer.total_processing_time
            else:
                processing_time = 0
                
            status_metadata = {
                "error": error_msg,
                "error_timestamp": timezone.now().isoformat(),
                "total_nodes_processed": self.timer.total_nodes_processed,
                "total_embeddings_generated": self.timer.total_embeddings_generated,
                "total_processing_time": processing_time
            }
            
            DataEmbedding.objects.filter(id=self.embedding_job.id).update(
                status=DataEmbedding.STATUS_ERROR,
                execution_end_at=timezone.now(),
                processing_error=error_msg,
                total_processing_time=processing_time,
                status_metadata=status_metadata
            )
            
        except Exception as handle_error:
            print(f"❌ Error handling error: {handle_error}")
            logger.add(f"Error handling error: {handle_error}")
            traceback.print_exc()


def main(embedding_job_id=None):
    """Main function to process nodes and generate embeddings"""
    try:
        if embedding_job_id:
            job = DataEmbedding.without_company_objects.get(id=embedding_job_id)
            
            CompanyUtils.set_company_registry(job.company)
            
            embedding_service = DataEmbeddingService(None, job)
            
            return embedding_service.process_embedding_job()
        else:
            pending_job = DataEmbedding.without_company_objects.filter(
                status=DataEmbedding.STATUS_PENDING
            ).order_by('created_at').first()
            
            if pending_job:
                CompanyUtils.set_company_registry(pending_job.company)
                
                embedding_service = DataEmbeddingService(None, pending_job)
                
                return embedding_service.process_embedding_job()
            else:
                print("No pending embedding jobs found")
                return False
    except Exception as e:
        error_msg = f"Error in main function: {e}"
        print(f"❌ {error_msg}")
        logger.add(error_msg)
        traceback.print_exc()
        return False