import unittest
import subprocess

class CommandlineTest(unittest.TestCase):
    def setUp(self):
        pass
        self.assertRun('python manage.py flush --noinput --settings=higlass_server.settings_test')

    def assertRun(self, command,  output_re=r''):
        self.assertRegexpMatches(subprocess.check_output(command , shell=True).strip(), output_re)

    def test_hello(self):
        self.assertRun('echo "hello?"', r'hello')

    def test_cli_upload(self):
        cooler = 'dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool'
        settings = 'higlass_server.settings_test'
        id = 'cli-test'
        self.assertRun('python manage.py ingest_tileset --filename data/'+cooler+' --datatype matrix --filetype cooler --uid '+id+' --settings='+settings)
        self.assertRun('curl -s http://localhost:6000/api/v1/tiles/?d='+id+'.1.1.1',
                       r'\{"cli-test.1.1.1": \{"max_value": 2.0264008045196533, "min_value": 0.0, "dense": "JTInPwAAAAAAA')

    def test_cli_huge_upload(self):
        cooler = 'huge.fake.cool'
        with open('data/'+cooler, 'w') as file:
            file.truncate(1024 ** 3)
        settings = 'higlass_server.settings_test'
        id = 'cli-huge-test'
        self.assertRun('python manage.py ingest_tileset --filename data/'+cooler+' --datatype foo --filetype bar --uid '+id+' --settings='+settings)
        self.assertRun('curl -s http://localhost:6000/api/v1/tiles/?d='+id+'.1.1.1',
                       r'\{"cli-test.1.1.1": \{"max_value": 2.0264008045196533, "min_value": 0.0, "dense": "OjkAAAAAAAA')
