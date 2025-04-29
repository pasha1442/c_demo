import subprocess
import time

import psutil
import redis
import requests
from decouple import config
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from health_check.exceptions import HealthCheckException
from health_check.plugins import plugin_dir
from backend.services.kafka_service import BaseKafkaService
from backend.settings.celery import app


class HealthCheckService():

    def __init__(self):
        self.health_checks = {
            "kafka": self.get_custom_kafka_health_status_using_topic,
            "db": self.get_custom_db_health_status,
            "cache": self.get_custom_cache_health_status,
            "redis": self.get_custom_redis_health_status,
            "storage": self.get_custom_storage_heallth_status,
            "migration": self.get_custom_migration_status,
            "celery": self.get_custom_celery_health_status,
            "url_health_checker": self.get_custom_url_health_status,
            "system_services_health_checker": self.get_system_service_status,
        }

    def get_health_check_status(self, health_list=[]):
        response = {}
        if health_list:
            for health in health_list:
                result = self.health_checks.get(health)()
                if health != 'url_health_checker' and health != 'system_services_health_checker':
                    response[health.upper()] = result
                else:
                    response.update(result)

        return response

    def dump_health_check_in_log_file(self, system_name=None):
        response = {}
        if system_name:
            get_system_health = self.health_checks.get(system_name)
            result = get_system_health()
            result["status"] = "Healthy" if result.get("status") else "Un-healthy"
            if system_name != "url":
                response[system_name.upper()] = result
            else:
                response.update(result)
        return response

    def get_custom_db_health_status(self):
        status = False
        message = ""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")  # Simple query to test the connection
                status = True
                message = "DB is healthy"
        except Exception as e:
            message = f"Not healthy: {str(e)}"

        return {"status": status, "message": message}

    def get_custom_cache_health_status(self):
        status = False
        message = ""
        try:
            # Attempt to set and retrieve a test value in the cache
            HEALTHCHECK_CACHE_KEY = config('HEALTHCHECK_CACHE_KEY', 'healthcheck_key')
            HEALTHCHECK_CACHE_KEY_VALUE = config('HEALTHCHECK_CACHE_KEY_VALUE', 'healthcheck_key_value')

            cache.set(HEALTHCHECK_CACHE_KEY, HEALTHCHECK_CACHE_KEY_VALUE, timeout=5)
            value = cache.get(HEALTHCHECK_CACHE_KEY)
            if value == HEALTHCHECK_CACHE_KEY_VALUE:
                status = True
                message = "Cache is working as expected"
            else:
                message = "Not healthy: Cache set/get failed"
        except Exception as e:
            message = f"Not healthy: {str(e)}"
        return {"status": status, "message": message}

    def get_custom_redis_health_status(self, timeout=5):
        try:
            # Create a connection to the Redis server
            REDIS_HOST = config('REDIS_HOST', default="127.0.0.1")
            REDIS_PORT = config('REDIS_PORT', default="6379")
            REDIS_USERNAME = config('REDIS_USERNAME', default=None)
            REDIS_PASSWORD = config('REDIS_PASSWORD', default=None)

            redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, socket_timeout=timeout,
                                             username=REDIS_USERNAME, password=REDIS_PASSWORD)

            # Perform a health check by setting and getting a test key
            test_key = config('REDIS_HEALTHCHECK_KEY', default="redis_health_check_key")
            test_value = config('REDIS_HEALTHCHECK_KEY_VALUE', default="redis_health_check_key_value")

            redis_client.set(test_key, test_value)  # Set key with expiration
            value = redis_client.get(test_key)  # Retrieve the key

            # Check if the value matches
            if value and value.decode('utf-8') == test_value:
                return {"status": True, "message": "Redis is working as expected."}
            else:
                return {"status": False, "message": "Redis test key mismatch."}
        except redis.ConnectionError as e:
            return {"status": False, "message": f"Redis connection failed: {str(e)}"}
        except redis.AuthenticationError:
            return {"status": False, "message": "Redis authentication failed. Check username/password."}
        except Exception as e:
            return {"status": False, "message": f"Redis health check failed: {str(e)}"}

    def get_custom_storage_heallth_status(self):
        status = False
        message = ""
        try:
            # Attempt to save and delete a test file and verify the storage health
            storage_file = config('STORAGE_TEST_FILE_NAME', default='health_check_test_file.txt')
            test_file = default_storage.save(storage_file, ContentFile('Test content'))
            default_storage.delete(test_file)
            status = True
        except Exception as e:
            # raise HealthCheckException(f"Storage backend is not healthy: {str(e)}")
            message = f"Storage backend is not healthy: {str(e)}"

        return {"status": status, "message": message}

    def get_custom_migration_status(self):
        """
        Checks if all migrations are applied.
        """
        status = False
        message = "No unapplied migration found"
        try:
            # Initialize the migration executor
            executor = MigrationExecutor(connection)

            # Get the list of unapplied migrations
            unapplied_migrations = executor.migration_plan(executor.loader.graph.leaf_nodes())
            status = True

            if unapplied_migrations:
                message = (f"Unapplied migrations found: {unapplied_migrations}")
                status = False
        except Exception as e:
            message = (f"Migration health check failed: {str(e)}")

        return {"status": status, "message": message}

    def get_custom_celery_health_status(self):
        status = False
        message = "Celery is healthy."
        try:
            # Ping Celery workers
            response = app.control.ping(timeout=1)

            if response:
                status = True
            else:
                message = "No workers replied"
        except Exception as e:
            message = str(e)
        return {"status": status, "message": message}

    def get_custom_url_health_status(custom_url="https://www.google.com"):

        url_list = config('HEALTH_CHECK_CUSTOM_URL_CHECKER', 'https://google.com')
        response = {}
        message = ""

        if url_list:
            url_list = url_list.split("|")
            for custom_url in url_list:
                status = False
                try:
                    url_response = requests.get(custom_url, timeout=5)
                    if url_response.status_code == 200:
                        status = True
                        message = f"URL {custom_url} is reachable"
                    else:
                        message = f"Status code {url_response.status_code}"
                except requests.RequestException as e:
                    message = str(e)
                response[custom_url] = {"status": status, "message": message}
        else:
            message = "URL not found."
            response["No Urls"] = {"status": False, "message": message}

        return response

    def get_custom_kafka_health_status_using_topic(self):
        status = False
        response_message = ""
        KAFKA_BROKER = config('KAFKA_HOST', default="localhost:9092").split(":")
        topic_name = "kafka_health_check"
        health_message = "Check Kafka Health"
        kafka_object = BaseKafkaService(topic_name=topic_name)

        try:
            producer = kafka_object.push(topic_name=topic_name, message=health_message)
            time.sleep(5)
            consumer = kafka_object.pull_message_with_timeout(topic_name=topic_name, timeout_sec=5)
            for c_message in consumer:
                message = c_message.value
                message = message.strip('"')
                if message == health_message:
                    response_message = "Kafka is healthy"
                    status = True
                    consumer.close()
                    kafka_object.delete_topics([topic_name])
                    print("Delete all message of this topic")
                    # Recreate topic to continue consuming
                    kafka_object.create_topic()
                    print("Create Topic again.")
                else:
                    response_message = "No health message found"
                    consumer.close()
                break  # Stop consuming

        except Exception as e:
            response_message = str(e)
        finally:
            consumer.close()

        return {"status": status, "message": response_message}

    def system_health_check(self):
        results = {}
        overall_status = True
        for plugin_tuple in plugin_dir._registry:

            plugin_class = plugin_tuple[0]  # Extract the plugin class
            config = plugin_tuple[1]  # Extract additional configuration (if any)
            # Instantiate and run the plugin
            plugin = plugin_class(**config) if config else plugin_class()

            try:
                status = plugin.run_check()  # Run the health check
                healthy = True
                message = "OK"
            except Exception as e:
                healthy = False
                message = str(e)

            # Add results to the response
            results[plugin.identifier()] = {
                'status': healthy,
                'message': message,
            }

            if not healthy:
                overall_status = False

            # Return the health status and checks
        return {"name": "DB", "health": overall_status, "message": message, "checks": results}

    def get_system_service_status(self):
        """
        Check if the service process is running. Works on Windows, macOS, and Linux.
        Also, this can provide the status true if the service exists in the system and running. Else in all case it
        return false Either service installed or not.
        """
        status = False  # Process not found
        service_list = config('HEALTH_CHECK_CUSTOM_SYSTEM_SERVICE_CHECKER', '')
        response = {}
        message = ""

        # running_services_list = self.get_all_running_system_services()

        if service_list:
            service_list = service_list.split("|")
            for services in service_list:
                try:
                    status = self.get_service_status(services)
                    services_name = services + " Service"
                    message = "not running"
                    if status:
                        status = True
                        message = "running"
                    response[services_name] = {"status": status, "message": f"{services_name} is {message}"}
                except Exception as e:
                    response[services_name] = {"status": False, "message": f"Failed to check status of {services_name}"}
        else:
            message = "Service list not found."
            response["No Services"] = {"status": status, "message": message}

        return response

    def get_all_running_system_services(self):
        running_services = []
        for process in psutil.process_iter(attrs=['pid', 'name', 'status']):
            if process.info['name'].lower() and process.info['status'] == 'running':
                running_services.append(process.info['name'].lower())

        return running_services

    def get_service_status(self, service_name):
        result = subprocess.run(
            ['systemctl', 'status', service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if service_name in result.stdout and "started" in result.stdout:
            return True
        else:
            return False,
