from kafka.admin import KafkaAdminClient, NewTopic
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from kafka.errors import KafkaError

from decouple import config
from basics.singleton import Singleton
import json
import hashlib

class BaseKafkaService(metaclass=Singleton):
    __producer_connection = None

    def __init__(self, topic_name=None):
        self.bootstrap_servers = config('KAFKA_HOST', default="localhost:9092")
        self.sasl_username = config('KAFKA_USERNAME', default='kafka_user')
        self.sasl_password = config('KAFKA_PASSWORD', default='kafka_password')
        self.sasl_mechanism = config('KAFKA_SASL_MECHANISM', default='PLAIN')
        self.security_protocol = config('KAFKA_SECURITY_PROTOCOL', default='SASL_PLAINTEXT')

        self.group_id = 'consumer_group_1'
        self.client_id = 'cygnus-kafka'
        self.topic_name = topic_name
        self.admin_client = KafkaAdminClient(
            bootstrap_servers=self.bootstrap_servers,  # Kafka broker address
            client_id=self.client_id,  # Client ID for the admin
            security_protocol=self.security_protocol,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_username=self.sasl_username,
            sasl_plain_password=self.sasl_password,
        )
        self.__producer_connection = KafkaProducer(
            bootstrap_servers=[self.bootstrap_servers],  # Kafka broker address
            security_protocol=self.security_protocol,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_username=self.sasl_username,
            sasl_plain_password=self.sasl_password,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Serialize messages as JSON
        )

    def create_topic(self):
        # Define the new topic (queue)
        new_topic = NewTopic(
            name=self.topic_name,
            num_partitions=1,  # For queue semantics, 1 partition ensures message ordering
            replication_factor=1  # Replication factor for redundancy
        )
        # Create the topic
        self.admin_client.create_topics(new_topics=[new_topic], validate_only=False)
        print(f"Topic '{self.topic_name}' created successfully.")
        # Close the admin client
        self.admin_client.close()

    def get_queue_list(self):
        topics = self.admin_client.list_topics()
        self.admin_client.close()
        return topics

    def get_queue_count(self):
        consumer = KafkaConsumer(
            bootstrap_servers=[self.bootstrap_servers],  # Kafka broker address
            auto_offset_reset='earliest',
            group_id=self.group_id,  # We don't need to track offset commits for this task
            enable_auto_commit=False,  # Disable auto-commit since we're not consuming messages

            # SASL
            security_protocol=self.security_protocol,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_username=self.sasl_username,
            sasl_plain_password=self.sasl_password
        )
        partition = 0  # Specify the partition
        # Assign the consumer to the specific partition
        tp = TopicPartition(self.topic_name, partition)
        consumer.assign([tp])

        # Fetch committed offsets for the group
        committed_offset = consumer.committed(tp)
        if committed_offset is None:
            committed_offset = 0  # If no committed offset, assume 0

        consumer.seek_to_end(tp)  # Move to the end
        latest_offset = consumer.position(tp)  # Get the latest offset
        unprocessed_count = latest_offset - committed_offset
        consumer.close()  # Always close the consumer
        return unprocessed_count

    def push(self, topic_name=None, message=None):
        try:
            """Producer"""
            # producer = KafkaProducer(
            #     bootstrap_servers=[self.bootstrap_servers],  # Kafka broker address
            #     value_serializer=lambda v: json.dumps(v).encode('utf-8')  # Serialize messages as JSON
            # )
            self.topic_name = topic_name if topic_name else self.topic_name
            self.__producer_connection.send(self.topic_name, value=message)
            self.__producer_connection.flush()
            # __producer_connection.close()
        except KafkaError as e:
            print(f"Error producing message: {e}")

    def pull(self, topic_name=None):
        """Consumer"""
        print("topic_name", topic_name)
        self.topic_name = topic_name if topic_name else self.topic_name
        consumer = KafkaConsumer(
            self.topic_name,  # Replace with your Kafka topic
            bootstrap_servers=[self.bootstrap_servers],  # Kafka broker address
            auto_offset_reset='earliest',  # Start reading at the earliest offset
            enable_auto_commit=True,  # Automatically commit offsets
            group_id=self.group_id,  # Consumer group ID
            # SASL
            security_protocol=self.security_protocol,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_username=self.sasl_username,
            sasl_plain_password=self.sasl_password,

            max_poll_interval_ms=600000,  # 600000 miliseconds = 10 minutes
            value_deserializer=lambda x: x.decode('utf-8')  # Decode messages
        )
        print("Waiting for messages...")
        return consumer
        # Consume messages from the topic
        # for message in consumer:
        #     print(f"Received message: {message.value}")

    def get_failure_queue_name(self, topic_name=None):
        self.topic_name = topic_name if topic_name else self.topic_name
        if self.topic_name:
            return f"failure_{self.topic_name}"
        return ""

    def get_hash_encoded_value(self, executor_partition_key):
        # Create a SHA-256 hash object
        sha256_hash = hashlib.sha256(executor_partition_key.encode())
        # Convert the hash to an integer
        unique_number = int(sha256_hash.hexdigest(), 16)
        return unique_number

    def pull_message_with_timeout(self, topic_name=None, timeout_sec=60*10):
        """Consumer"""
        print("topic_name", topic_name)
        self.topic_name = topic_name if topic_name else self.topic_name
        poll_interval = timeout_sec*1000
        print("poll_interval", poll_interval)
        consumer = KafkaConsumer(
            self.topic_name,  # Replace with your Kafka topic
            bootstrap_servers=[self.bootstrap_servers],  # Kafka broker address
            auto_offset_reset='earliest',  # Start reading at the earliest offset
            enable_auto_commit=True,  # Automatically commit offsets
            group_id=self.group_id,  # Consumer group ID
            # SASL
            security_protocol=self.security_protocol,
            sasl_mechanism=self.sasl_mechanism,
            sasl_plain_username=self.sasl_username,
            sasl_plain_password=self.sasl_password,

            max_poll_interval_ms=poll_interval,  # 600000 miliseconds = 10 minutes
            value_deserializer=lambda x: x.decode('utf-8'),  # Decode messages
            consumer_timeout_ms = poll_interval
        )
        print("Waiting for messages...")
        return consumer

    def delete_topics(self, topic_names=[]):
        if topic_names:
            self.admin_client.delete_topics(topics=topic_names)
            print(f"Delete all message of the topics {topic_names}")
