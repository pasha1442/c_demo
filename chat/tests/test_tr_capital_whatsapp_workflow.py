import unittest
from basics.base_testing.base_testing import QueueBasedTestCases


class TestTRCapital(QueueBasedTestCases):
    @classmethod
    def setUpClass(cls):
        """Set up Kafka test_old resources."""
        cls.topic_name = "test_whatsapp_request_message_queue"

    def test_first_whatsapp_workflow_producer(self):
        test_message = self.get_sample_message_by_company(company_name=self.TR_CAPITAL)
        response = self.push_test_message(topic_name=self.topic_name, message=test_message)
        if response.get("status"):
            self.assertTrue(True)
            print("TR Capital | Whatsapp Workflow Producer | Success")
        else:
            print(f"TR Capital | Whatsapp Workflow Producer | Failed | ERROR: {response.get('message')}")
            self.assertFalse(True)

    def test_second_consume_whatsapp_workflow(self):
        response = self.pull_test_message(topic_name=self.topic_name)
        if response.get("status"):
            message = response.get("message")
            response = self.handle_message_for_test(topic_name=self.topic_name, message=message)

        if response.get("status"):
            self.assertTrue(True)
            print("TR Capital | Whatsapp Workflow Consumer | Success")
        else:
            print(f"TR Capital | Whatsapp Workflow Consumer | Failed | ERROR: {response.get('message')}")
            self.assertFalse(True)


def suite():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Load all tests from the test case class
    all_tests = loader.loadTestsFromTestCase(TestTRCapital)

    # Sort tests based on their method names
    sorted_tests = sorted(all_tests, key=lambda test: test._testMethodName)

    suite.addTests(sorted_tests)
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner().run(suite())
