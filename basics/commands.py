import logging
import sys
from django.core.management.base import BaseCommand
from backend.logger import LoggerWriter

class BaseCommand(BaseCommand):
    
    def init_logger(self, logger_name):
        logger = logging.getLogger(logger_name)
        
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            logger.addHandler(console_handler)
        
        sys.stdout = LoggerWriter(logger.info)
        sys.stderr = LoggerWriter(logger.error)