from celery import shared_task
from celery import Task

from chat.services.kafka_workflow_response_handler import KafkaWorkflowResponseHandler, WahaMessageState


class CeleryService:
    """
    A class to manage dynamic Celery task creation and scheduling.
    """

    class WrappedTask(Task):
        """A base Celery task for dynamic execution."""

        def run(self, *args, **kwargs):
            task_name = kwargs.pop("task_name", "Unnamed Task")
            print(f"Executing {task_name} with args: {args} and kwargs: {kwargs}")
            return f"{task_name} executed successfully!"

    @staticmethod
    @shared_task(base=WrappedTask)
    def dynamic_task(task_name, *args, **kwargs):
        """Shared task logic."""
        args = kwargs.get("args", ())
        kwargs = kwargs.get("kwargs", {})
        if kwargs:
            _func_name = kwargs.get("func_name", None)
            class_name, method_name = _func_name.split('.')
            # Dynamically import the class
            cls = globals()[class_name]
            method = getattr(cls, method_name)
            method(*args)
        print("Task Executed with Task Name: ", task_name)

    def schedule_task(self, task_name, countdown, *args, **kwargs):
        """Schedule the dynamic task with a delay."""
        kwargs["task_name"] = task_name  # Include task_name in kwargs
        self.dynamic_task.apply_async(task_name=task_name, args=args, kwargs=kwargs, countdown=countdown)


class CeleryTools:

    @staticmethod
    def workflow_execution_checker(args):
        from chat.services.consumer_services.kafka_workflow_consumer_service import CeleryWorkflowConsumer
        CeleryWorkflowConsumer.check_and_execute_workflow(args)
        
    @staticmethod  
    def send_message_to_waha_queue(type, mobile_number, message, waha_session):
        print("\n\nsend message started", mobile_number, message, waha_session)
        waha_message = WahaMessageState(type=type, mobile_number=mobile_number, message=message, waha_session=waha_session)
        KafkaWorkflowResponseHandler().push_waha_message_to_queue(waha_message=waha_message)
        print("\n\n\npushed message through celery")