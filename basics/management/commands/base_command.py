from django.core.management.base import BaseCommand
from decouple import config
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


class BaseManagementCommand(BaseCommand):

    def __init__(self):
        pass

    def start_n_consumer(self, topics, func):
        consumer_thread_count = int(config('CONSUMER_THREAD_COUNT', default=5))
        print(f"- Starting with CPU CORE:{consumer_thread_count}")
        with ProcessPoolExecutor(max_workers=consumer_thread_count) as exe:
            for j in range(0, consumer_thread_count):
                exe.submit(self.start_consumer, topics, func)
