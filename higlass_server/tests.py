import unittest
import subprocess

class CommandlineTest(unittest.TestCase):
    def setUp(self):
        pass

    def assertRun(self, command,  output_re):
        self.assertRegexpMatches(subprocess.check_output(command , shell=True).strip(), output_re)

    def test_hello(self):
        self.assertRun('echo "hello?"', r'hello')