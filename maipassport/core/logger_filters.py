import logging


class RequestUserFilter(logging.Filter):

    def filter(self, record):
        record.user_type = 'None'
        record.user_id = 0
        # if hasattr(record, 'request') and hasattr(record.request, 'user_type'):
        #     record.user_type = record.request.user_type
        #     # if record.user_type != 'OfflineSys':
        #     if record.user_type not in ['Mai', 'OfflineSys']:
        #         record.user_id = record.request.user_object.id
        return True
