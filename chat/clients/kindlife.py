from chat import clients
from .base import BaseOrganization
import chat.utils as utils
import chat.assistants as assistants
import requests
import os


class Kindlife(BaseOrganization):
    def process_request(self, request, text, mobile):
        chat_history = utils.fetch_conversation(request.user, mobile)

        # todo
        # before fetching get user specifc data from client
        master_response = assistants.get_active_master_prompt(request, chat_history)
        role = master_response.get('role', 'assistant')
        function_name = master_response.get('function_name', '')
        utils.save_conversation(request.user, role, mobile, master_response['message'],
                                {'function_name': function_name})

        if 'is_function' in master_response and master_response['is_function'] == True:
            if master_response['function_name'] == "designate_to_order_assistant":
                # todo dynamic service id?
                # if not utils.has_service(request.user,2):
                #     return "You have not opted for order support"
                chat_history = utils.fetch_conversation(request.user, mobile)
                order_response = assistants.get_active_order_prompt(request, chat_history)
                if 'is_function' in order_response and order_response['is_function'] == True:
                    if order_response['function_name'] == "get_recent_orders":
                        recent_order_data = self.recent_orders(request)
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'get_recent_orders',
                                                 'function_return': recent_order_data})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        order_response = assistants.get_active_order_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, order_response['completion'])
                        master_response['message'] = order_response['completion']
                    elif order_response['function_name'] == "get_order_info":
                        order_data = self.order_data(request.user, order_response['arguments']['order_id'])
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'get_order_info', 'function_return': order_data})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        order_response = assistants.get_active_order_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, order_response['completion'])
                        master_response['message'] = order_response['completion']
                    elif order_response['function_name'] == "get_shipment_info":
                        shipment_data = self.shipment_info(request.user, order_response['arguments']['shipment_id'])
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'get_shipment_info',
                                                 'function_return': shipment_data})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        shipment_response = assistants.get_active_order_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, shipment_response['completion'])
                        master_response['message'] = shipment_response['completion']
                    elif order_response['function_name'] == "create_ticket":
                        ticket_params = {'customer_id': 629}
                        if 'order_id' in order_response:
                            ticket_params['order_id'] = order_response['order_id']
                        ticket_data = self.ticket_handler(request.user, ticket_params)
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'create_ticket', 'function_return': ticket_data})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        ticket_response = assistants.get_active_order_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, ticket_response['completion'])
                        master_response['message'] = ticket_response
                    elif order_response['function_name'] == "cancel_order":
                        cancel_data = self.cancel_order(request.user, order_response['arguments']['order_id'])
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'cancel_order', 'function_return': cancel_data})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        cancel_response = assistants.get_active_order_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, cancel_response['completion'])
                        master_response['message'] = cancel_response['completion']
                else:
                    utils.save_conversation(request.user, 'assistant', mobile, order_response['completion'])
                    master_response['message'] = order_response['completion']
            elif master_response['function_name'] == "designate_to_brand_support_assistant":
                # if not utils.has_service(request.user,4):
                #     return "You have not opted for brand onboarding support"
                chat_history = utils.fetch_conversation(request.user, mobile)
                bot_response = assistants.get_active_brand_support_prompt(request, chat_history)
                if 'is_function' in bot_response and bot_response['is_function'] == True:
                    if bot_response['function_name'] == "create_brand_onboarding_ticket":
                        brand_ticket = self.ticket_handler(request.user, bot_response['arguments'])
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'create_brand_onboarding_ticket',
                                                 'function_return': brand_ticket})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        brand_onb_response = assistants.get_active_brand_support_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, brand_onb_response['completion'])
                        master_response['message'] = brand_onb_response
            elif master_response['function_name'] == "designate_to_bulk_order_support_assistant":
                # if not utils.has_service(request.user,2):
                #     return "You have not opted for bulk order support"
                chat_history = utils.fetch_conversation(request.user, mobile)
                bot_response = assistants.get_active_bulk_order_support_prompt(request, chat_history)
                if 'is_function' in bot_response and bot_response['is_function'] == True:
                    if bot_response['function_name'] == "create_ticket_bulk_order":
                        bulk_order_ticket = self.ticket_handler(request.user, bot_response['arguments'])
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'create_ticket_bulk_order',
                                                 'function_return': bulk_order_ticket})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        bulk_order_response = assistants.get_active_bulk_order_support_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, bulk_order_response['completion'])
                        master_response['message'] = bulk_order_response
            elif master_response['function_name'] == "designate_to_corporate_gifting_support_assistant":
                # if not utils.has_service(request.user,5):
                #     return "You have not opted for corporate gifting support"
                chat_history = utils.fetch_conversation(request.user, mobile)
                bot_response = assistants.get_active_corp_gifting_support_prompt(request, chat_history)
                if 'is_function' in bot_response and bot_response['is_function'] == True:
                    if bot_response['function_name'] == "create_ticket_corp_gifting":
                        corp_gifting_ticket = self.ticket_handler(request.user, bot_response['arguments'])
                        utils.save_conversation(request.user, 'function', mobile, master_response['message'],
                                                {'function_name': 'create_ticket_corp_gifting',
                                                 'function_return': corp_gifting_ticket})
                        chat_history = utils.fetch_conversation(request.user, mobile)
                        corp_gifting_response = assistants.get_active_corp_gifting_support_prompt(request, chat_history)
                        utils.save_conversation(request.user, 'assistant', mobile, corp_gifting_response['completion'])
                        master_response['message'] = corp_gifting_response
            elif master_response['function_name'] == "designate_to_expert_assistant":
                # if not utils.has_service(request.user,6):
                #     return "You have not opted for expert support"
                chat_history = utils.fetch_conversation(request.user, mobile)
                expert_response = assistants.get_active_expert_support_prompt(request, chat_history)
                if 'is_function' in expert_response and expert_response['is_function'] == True:
                    if expert_response['function_name'] == "product_search":
                        # fetch recent order data for a user
                        # todo
                        pass
                    elif expert_response['function_name'] == "personalised_web_link":
                        # todo
                        pass
                else:
                    utils.save_conversation(request.user, 'assistant', mobile, expert_response['completion'])
                    master_response['message'] = expert_response['completion']

        return master_response

    def recent_orders(self, client):
        endpoint = "https://api.kindlife.in/api/orders/"
        # todo find user_id form mobile and supply as parameter
        params = {
            'items_per_page': 5,
            'user_id': 629
        }
        bearer_token = os.getenv("KL_TOKEN")
        headers = {
            'Authorization': f"Bearer {bearer_token}"
        }

        response = requests.get(endpoint, headers=headers, params=params)
        data = response.json()
        simplified_orders = []
        for order in data['orders']:
            new_order = {
                'order_id': order['order_id'],
                'order_date': order['timestamp_converted'],
                'status': order['status']
            }
            simplified_orders.append(new_order)

        return simplified_orders

    def order_data(self, client, order_id):
        endpoint = f"https://api.kindlife.in/api/orders/{order_id}"
        bearer_token = os.getenv("KL_TOKEN")
        headers = {
            'Authorization': f"Bearer {bearer_token}"
        }
        response = requests.get(endpoint, headers=headers)
        data = response.json()
        # todo add product data
        simplified_order = {
            'order_id': data['order_id'],
            'total': data['total'],
            'subtotal': data['subtotal'],
            'discount': data['discount'],
            'payment_surcharge': data['payment_surcharge'],
            'shipping_cost': data['shipping_cost'],
            'timestamp': data['timestamp'],
            'status': data['status'],
            'firstname': data['firstname'],
            'lastname': data['lastname'],
            'email': data['email'],
            'phone': data['phone'],
            'shipping_phone': data['s_phone'],
            'address_type': data['s_address_type'],
            'ip_address': data['ip_address'],
            'products_delivery_date': data['products_delivery_date'],
        }

        return simplified_order

    def cancel_order(self, client, order_id):
        endpoint = f"https://api.kindlife.in/api/orders/{order_id}"
        bearer_token = os.getenv("KL_TOKEN")
        headers = {
            'Authorization': f"Bearer {bearer_token}"
        }
        response = requests.get(endpoint, headers=headers)
        data = response.json()
        order_status = data['status']
        params = {}
        if order_status in ['P', 'O', 'G', 'F', 'M', 'R']:
            cancellable = True
            # todo
            # fn_change_order_status(order_data['order_id'], 'H')
            params['text'] = "Cancellation request is complete"
        elif order_status == 'I':
            # I - Cancelled
            params['text'] = "Order is already cancelled."
        elif order_status == 'H':
            # H - Cancellation requested by customer
            params['text'] = "Cancellation request is noted."
        elif order_status == 'C':
            # C - Completed
            params['text'] = "Order is not eligible for cancellation."
        else:
            # Default case for other statuses
            params['text'] = "Order is already shipped, Create a support ticket by taking consent of user."

        return params['text']

    def shipment_info(self, client, shipment_id):
        endpoint = f"https://api.kindlife.in/api/shipments/{shipment_id}"
        bearer_token = os.getenv("KL_TOKEN")
        headers = {
            'Authorization': f"Bearer {bearer_token}"
        }
        response = requests.get(endpoint, headers=headers)
        data = response.json()
        return data

    def ticket_handler(self, client, args):
        if args.get('customer_id'):
            customer_id = args['customer_id']
            args['order_id'] = args.get('order_id', 0)
            query = '&'.join(f"{key}={value}" for key, value in args.items())
            base_url = f"https://www.kindlife.in/api/tickets/{customer_id}?{query}"
            bearer_token = os.getenv("KL_TOKEN")
            access_token = f"Bearer {bearer_token}"

            headers = {
                "Authorization": access_token,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            response = requests.get(base_url, headers)

            res = response.json()
            if 'status' not in res or res['status'] != 404:
                if 'id' in res[0] and res[0]['status'] != 'C':
                    args['ticket_id'] = res[0]['id']
                    new_threads = self.update_ticket(clients, args)
                    if 'thread_id' in new_threads:  # type: ignore
                        return {
                            "ticket_id": new_threads['ticket_id'],  # type: ignore
                            "message": new_threads['message'],  # type: ignore
                            "action": "Ticket Updation"
                        }
                else:
                    new_ticket = self.create_ticket(client, args)
                    if 'ticket_id' in new_ticket:  # type: ignore
                        return {
                            "ticket_id": new_ticket['ticket_id'],  # type: ignore
                            "message": new_ticket['message'],  # type: ignore
                            "action": "Ticket Creation"
                        }

    def create_ticket(self, client, params):
        # Properly formatted URL with protocol
        endpoint = "https://api.kindlife.in/api/tickets"

        # todo
        payload = {
            "ticket_data": {
                "user_id": "629",
                "ticket_type": "15",
                "subject": "test",
                "order_id": "0",
                "message": "testing"
            }
        }
        bearer_token = os.getenv("KL_TOKEN")
        access_token = f"Bearer {bearer_token}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"{access_token}"
        }

        # todo check if ticket already exists before creating new
        response = requests.post(endpoint, headers=headers, json=payload)

        # Error handling
        if response.status_code == 200:
            print("Success:", response.text)
        else:
            print("Error:", response.status_code, response.text)
        # todo 
        return True

    def update_ticket(self, client, params):
        endpoint = f"https://api.kindlife.in/api/tickets{params.ticket_id}"

        # todo
        payload = {
            "action": "ticket_reply",
            "ticket_status": 'U',
            "ticket_data": {
                "user_id": "629",
                "message": "testing"
            }
        }
        bearer_token = os.getenv("KL_TOKEN")
        access_token = f"Bearer {bearer_token}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"{access_token}"
        }
        response = requests.put(endpoint, headers=headers, json=payload)
        return response

    def get_ticket_info(self, client, args):
        data = {}
        if 'customer_id' in args and 'ticket_id' in args:
            ticket_id = args.get('ticket_id', 0)
            base_url = f"https://api.kindlife.in/api/tickets/{args['customer_id']}?ticket_id={ticket_id}"
            bearer_token = os.getenv("KL_TOKEN")
            access_token = f"Bearer {bearer_token}"

            headers = {
                "Authorization": access_token,
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            response = requests.get(base_url, headers=headers)
            res = response.json()

            if res.get('status') != 404:
                for ticket in res:
                    data['ticket_id'] = ticket['id']

            else:
                data['message'] = 'Something went wrong, please try after sometime.'

            return data
