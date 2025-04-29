import importlib


class BaseResponseProcessor:

    def __init__(self):
        print("init function")

    def call_corresponding_response_processor(self, class_name, data):
        fully_qualified_name = f'services.response_processor.{class_name}'
        module_name, class_name = fully_qualified_name.rsplit('.', 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name, None)
        if cls:
            _res = cls().process_response(data)
            return _res


class KindLifeGETOrderProcessor(BaseResponseProcessor):

    def __init__(self):
        pass

    def process_response(self, data):
        simplified_orders = []
        for order in data['orders']:
            new_order = {
                'order_id': order['order_id'],
                'order_date': order['timestamp_converted'],
                'status': order['status']
            }
            simplified_orders.append(new_order)
        return simplified_orders
