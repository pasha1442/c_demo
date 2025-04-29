import unittest


class BaseUnitTestCase(unittest.TestCase):
    def setUp(self):
        print("Setting up the base test case")

    def tearDown(self):
        print("Tearing down the base test case")
        # Do some common cleanup
