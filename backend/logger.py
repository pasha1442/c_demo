import logging


class LoggerWriter:
    def __init__(self, log_func):
        self.log_func = log_func

    def write(self, message):
        if message.strip():  # Avoid printing empty messages
            self.log_func(message.strip())

    def flush(self):
        pass  # No flush required for logging


class Logger:
    DEBUG_LOG = "debug"
    INFO_LOG = 'info'
    ERROR_LOG = 'error_logger'
    REDIS_LOG = 'redis_info'
    WORKFLOW_LOG = 'workflow_info'
    OPENMETER_LOG = 'openmeter_info'
    HEALTH_LOG = 'health_info'
    FAILURE_QUEUE_LOG = 'failure_queue_info'
    DYNAMIC_HOOK_INFO = 'dynamic_hook_info'
    LONG_TERM_MEMORY_GENERATION_INFO = 'long_term_memory_generation_info'

    def __init__(self, logger_name=None):
        self.logger = logging.getLogger(logger_name or __name__)

    def add(self, message, level='INFO', *args, **kwargs):
        log_level = self.logger.level if self.logger.level else level
        if log_level is None or type(log_level) == str:
            log_level = getattr(logging, log_level, None)
            if log_level is None:
                # If the level doesn't exist, fallback to INFO level
                self.logger.warning(f"Invalid log level: {level}. Using INFO level instead.")
                log_level = logging.INFO

        # Log the message at the dynamically chosen log level
        self.logger.log(log_level, message, *args, **kwargs)
