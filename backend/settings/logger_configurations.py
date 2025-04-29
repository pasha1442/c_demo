from .base import LOG_FILES_ROOT, FAILURE_QUEUE_LOG_FILES_ROOT
import os
from logging.handlers import RotatingFileHandler
from logging.handlers import TimedRotatingFileHandler
from basics.logger import SeverityJsonFormatter
import logging
from logging import INFO

log_rotation_config = {"interval": 15, "backupCount": 5}

# Define a custom log level for health checks

WORKFLOW_LOG_LEVEL = 5
OPENMETER_LOG_LEVEL = 6
REDIS_LOG_LEVEL = 15
HEALTH_LOG_LEVEL = 25
FAILURE_QUEUE_LOG_LEVEL = 7


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        '': {
            'handlers': ['error', 'info', 'debug'],
            'level': INFO,
            'propagate': True,
        },
        'openmeter_info': {
             'handlers': ['openmeter_log', 'console'],
             'level':  INFO,
             'propagate': True,  # Prevent propagation to other handlers
                         },
        'workflow_info': {
            'handlers': ['workflow_log'],
            'level': INFO,
            'propagate': False,  # Prevent propagation to other handlers
        },
        'redis_info': {
            'handlers': ['redis_log'],
            'level': INFO,
            'propagate': False,  # Prevent propagation to other handlers
        },
        'health_info': {
            'handlers': ['health_log'],
            'level': HEALTH_LOG_LEVEL,
            'propagate': False,  # Prevent propagation to other handlers
        },
        'failure_queue_info': {
            'handlers': ['failure_queue_log'],
            'level': FAILURE_QUEUE_LOG_LEVEL,
            'propagate': False,  # Prevent propagation to other handlers
        },
        'dynamic_hook_info': {
             'handlers': ['dynamic_hook_log', 'console'],
             'level':  INFO,
             'propagate': True,  # Prevent propagation to other handlers
        },
        'long_term_memory_generation_info': {
             'handlers': ['long_term_memory_generation_log', 'console'],
             'level':  INFO,
             'propagate': True,  # Prevent propagation to other handlers
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        },
        'info': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'info.log'),
            'level': 'INFO',
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'error': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'error.log'),
            'level': 'ERROR',
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'debug': {
            # 'class': 'logging.handlers.RotatingFileHandler',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'debug.log'),
            'level': 'DEBUG',
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
            # 'maxBytes': 1024 * 1024 * 5,  # 5 MB
            # 'backupCount': 5,  # Keep 5 old log files
        },
        'openmeter_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'openmeter.log'),
            'level': INFO,
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'workflow_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'workflow.log'),
            'level': INFO,  # 'INFO',
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'redis_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'redis_log.log'),
            'level': INFO,  # 'INFO',
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'health_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'health_log.log'),
            'level': HEALTH_LOG_LEVEL,
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'failure_queue_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(FAILURE_QUEUE_LOG_FILES_ROOT), 'failure_queue_log.log'),
            'level': FAILURE_QUEUE_LOG_LEVEL,
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'dynamic_hook_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'dynamic_hook.log'),
            'level': INFO,
            'formatter': 'json',

            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        },
        'long_term_memory_generation_log': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(str(LOG_FILES_ROOT), 'long_term_memory_generation.log'),
            'level': INFO,
            'formatter': 'json',
            'when': 'midnight',  # Rotate logs every midnight
            'interval': 1,  # Rotate every 1 day
            'backupCount': 5,  # Keep 5 days of logs
        }
    },
    'formatters': {
        'default': {
            'format': '%(asctime)s [%(module)s | %(levelname)s] %(message)s',
        },
        'error': {
            'format': '%(asctime)s [%(module)s | %(levelname)s] %(message)s @ %(pathname)s : %(lineno)d : %(funcName)s',
        },
        'json': {
            '()': SeverityJsonFormatter,
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s %(filename)s %(lineno)d',
        },
    },
}
