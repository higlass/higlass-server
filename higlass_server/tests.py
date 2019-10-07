import unittest
import slugid
import subprocess

import tilesets.models as tm

class CommandlineTest(unittest.TestCase):
    def setUp(self):
        # TODO: There is probably a better way to clear data from previous test runs. Is it even necessary?
        # self.assertRun('python manage.py flush --noinput --settings=higlass_server.settings_test')
        pass

    def assertRun(self, command,  output_res=[]):
        output = subprocess.check_output(command , shell=True).decode('utf-8').strip()
        for output_re in output_res:
            self.assertRegexpMatches(output, output_re)
        return output

    def test_hello(self):
        self.assertRun('echo "hello?"', [r'hello'])

    def test_bamfile_upload_with_index(self):
        settings = 'higlass_server.settings_test'
        uid = slugid.nice()

        self.assertRun('python manage.py ingest_tileset' +
        ' --filename data/SRR1770413.mismatched_bai.bam' +
        ' --indexfile data/SRR1770413.different_index_filename.bai' +
        ' --datatype reads' +
        ' --filetype bam' +
        ' --uid '+uid+' --settings='+settings)

        self.assertRun('python manage.py shell ' +
            '--settings ' + settings +
            ' --command="' +
            'import tilesets.models as tm; '+
            f'o = tm.Tileset.objects.get(uuid=\'{uid}\');'
            'print(o.indexfile)"', '.bai$')

    def test_bamfile_upload_without_index(self):
        settings = 'higlass_server.settings_test'
        uid = slugid.nice()

        self.assertRun('python manage.py ingest_tileset' +
        ' --filename data/SRR1770413.sorted.short.bam' +
        ' --datatype reads' +
        ' --filetype bam' +
        ' --uid '+uid+' --settings='+settings)

        self.assertRun('python manage.py shell ' +
            '--settings ' + settings +
            ' --command="' +
            'import tilesets.models as tm; '+
            f'o = tm.Tileset.objects.get(uuid=\'{uid}\');'
            'print(o.indexfile)"', '.bai$')

    def test_cli_upload(self):
        cooler = 'dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool'
        settings = 'higlass_server.settings_test'
        id = 'cli-test'
        self.assertRun('python manage.py ingest_tileset --filename data/'+cooler+' --datatype matrix --filetype cooler --uid '+id+' --settings='+settings)
        self.assertRun('curl -s http://localhost:6000/api/v1/tileset_info/?d='+id,
                       [r'"name": "'+cooler+'"'])
        self.assertRun('curl -s http://localhost:6000/api/v1/tiles/?d='+id+'.1.1.1',
                       [r'"'+id+'.1.1.1":',
                        r'"max_value": 2.0264008045196533',
                        r'"min_value": 0.0',
                        r'"dense": "JTInPwAA'])

    def test_cli_huge_upload(self):
        cooler = 'huge.fake.cool'
        with open('data/'+cooler, 'w') as file:
            file.truncate(1024 ** 3)
        settings = 'higlass_server.settings_test'
        id = 'cli-huge-test'
        self.assertRun('python manage.py ingest_tileset --filename data/'+cooler+' --datatype foo --filetype bar --uid '+id+' --settings='+settings)
        self.assertRun('curl -s http://localhost:6000/api/v1/tileset_info/?d='+id,
                       [r'"name": "'+cooler+'"'])
        self.assertRun('curl -s http://localhost:6000/api/v1/tiles/?d='+id+'.1.1.1',
                       [r'"'+id+'.1.1.1"'])

        '''
        id = 'cli-coord-system-test'
        self.assertRun('python manage.py ingest_tileset --filename data/'+cooler+' --datatype foo --filetype bar --uid '+id+' --settings='+settings, 'coordSystem')
        self.assertRun('curl -s http://localhost:6000/api/v1/tileset_info/?d='+id,
                       [r'"coordSystem": "'+cooler+'"'])
        '''
        # TODO: check the coordSystem parameters for ingest_tileset.py

    def test_get_from_foreign_host_file(self):
        # manage.py should have been started with
        # export SITE_URL=somesite.com
        #self.assertRun('curl -s -H "Host: someothersite.com" http://localhost:6000/api/v1/tilesets/', [r'400'])
        #self.assertRun('curl -s -H "Host: somesite.com" http://localhost:6000/api/v1/tilesets/', [r'count'])
        pass

