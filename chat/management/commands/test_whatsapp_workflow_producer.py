from django.core.management.base import BaseCommand
from backend.services.kafka_service import BaseKafkaService


class Command(BaseCommand):
    help = "Kafka Workflow Consumer"

    # def add_arguments(self, parser):
    #     parser.add_argument('topic', type=str)

    def handle(self, *args, **options):
        try:

            # for i in range(1,100):
            message = f"please disable new_session1"
            data = {'source': 'whatsapp', 'service_provider_company': 'Meta',
                    'company_phone_number': '919467472222', 'company_id': 9,
                    'sender': '918560040957', 'message_id': 'wamid.HBgMOTE4NTYwMDQwOTU3FQIAEhgUM0FERDVEQTVCMTI3MDY4MzZCRkUA',
                    'message': message, 'message_type': 'text', 'media_url': None,
                    'timestamp': '', 'transaction_id': '01JE3DXWJ9GB9BHQ9PPC6XRT6Y'}
            
            waha_data = {'source': 'waha', 'service_provider_company': 'Meta',
                    'company_phone_number': '919352647179', 'company_id': 7,
                    'sender': '919352647179', 'message_id': 'wamid.HBgMOTE4NTYwMDQwOTU3FQIAEhgUM0FERDVEQTVCMTI3MDY4MzZCRkUA',
                    'message': message, 'message_type': 'text', 'media_url': None,
                    'timestamp': '', 'transaction_id': '01JE3DXWJ9GB9BHQ9PPC6XRT6Y', 'waha_session':'new_session1'}
            
            data1 = {'source': 'whatsapp', 'service_provider_company': 'Meta', 'company_phone_number': '919467472222',
                        'company_id': 9, 'sender': '918560040957',
                        'message_id': 'wamid.HBgMOTE4NTYwMDQwOTU3FQIAEhgWM0VCMEM4RjhCRUI1RjgxMUJCNzg5MQA=',
                        'message': None, 'message_type': 'image',
                        'media_url': 'https://storage.googleapis.com/ca-prod-customerdata/images/None/2024/12/2/wamid.HBgMOTE4NTYwMDQwOTU3FQIAEhgWM0VCMEM4RjhCRUI1RjgxMUJCNzg5MQA%3D_1733139289.jpeg', 'timestamp': '', 'transaction_id': '01JE3JDP60KVJ911BRACCFMAZ3'}


            waha_data['client_identifier'] = waha_data['sender']
            data1['client_identifier'] = data1['sender']
            print("data", type(data), data)

            BaseKafkaService().push(topic_name="waha_request_message_queue", message=waha_data)
            # BaseKafkaService().push(topic_name="whatsapp_request_message_queue", message=data1)
                # self.stdout.write(self.style.SUCCESS("started"))
                # company = CompanyUtils.get_company_from_company_id(3)
                # res = BaseAgent(company=company, agent_slug="api_agent.get_ongoing_incidents").invoke_agent(args={}, ai_args={})
                # print("test", res)

            self.stdout.write(self.style.SUCCESS("Executed"))
        except Exception as ex:
            self.stdout.write(self.style.ERROR(str(ex)))
