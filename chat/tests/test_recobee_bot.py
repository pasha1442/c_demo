from basics.base_testing.base_testing import APIBasedTestCases


class TestRecoBeeBot(APIBasedTestCases):

    def setUp(self):
        # This method will run before each test
        self.endpoint = "/api/v1/api-controller/invoke-service/recobee-chat/"
        self.api_url = self.core_server_base_url + self.endpoint
        self.headers = self.get_bot_header(company_name=self.RECOBEE)
        self.payload = self.generate_bot_payload(message="Hi")
        super().setUp()

    def test_auriga_bot(self):
        response = self.post_api_request(base_url=self.api_url, payload=self.payload, headers=self.headers,
                                         wait_for_full_response=True)
        status = response.get("status")
        error_message = response.get("error_message")
        status_code = response.get("status_code")
        text_response = response.get("text_response")

        if status and status_code == 200:
            print(f"RECOBEE | RECOBEE Bot Test | Success {text_response}")
            self.assertEqual(status_code, 200)

        else:
            print(f"RECOBEE | RECOBEE Bot Test | Failed | Error : {error_message}")
            self.assertEqual(status_code, 200)


