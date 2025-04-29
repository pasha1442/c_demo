from pythonjsonlogger import jsonlogger


class SeverityJsonFormatter(jsonlogger.JsonFormatter):

    def add_fields(self, log_record, record, message_dict):
        super(SeverityJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['severity'] = record.levelname