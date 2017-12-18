from __future__ import print_function

import cooler.contrib.higlass as cch

import django.core.files as dcf
import django.core.files.uploadedfile as dcfu
import django.contrib.auth.models as dcam
import django.db as db

import base64
import django.test as dt
import h5py
import json
import logging
import os.path as op
import numpy as np
import rest_framework.status as rfs
import tilesets.tiles as tt
import tilesets.models as tm
import higlass_server.settings as hss
import tilesets.generate_tiles as tgt


logger = logging.getLogger(__name__)


class TileTests(dt.TestCase):
    def test_partitioning(self):
        result = tgt.partition_by_adjacent_tiles(["a.5.0.0", "a.5.0.10"])

        assert(len(result) == 2)

        result = tgt.partition_by_adjacent_tiles(["a.5.0.0", "a.5.0.10", "a.5.0.11"])

        assert(len(result) == 2)

        result = tgt.partition_by_adjacent_tiles(["a.5.0.0", "a.5.0.10", "a.5.0.11", "a.7.11"])

        assert(len(result) == 3)

        result = tgt.partition_by_adjacent_tiles(["a.5.0", "a.5.1", "a.5.2"])

        assert(len(result) == 1)


class ChromosomeSizes(dt.TestCase):
    def test_list_chromsizes(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        upload_file = open('data/chromSizes.tsv', 'rb')
        self.chroms = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(
                upload_file.name, upload_file.read()
            ),
            filetype='chromsizes-csv',
            datatype='chromsizes',
            coordSystem="hg19",
            owner=self.user1,
            uuid='cs-hg19'
        )

        ret = json.loads(
            self.client.get(
                '/api/v1/available-chrom-sizes/'
            ).content.decode('utf-8')
        )

        assert(ret["count"] == 1)
        assert(len(ret["results"]) == 1)

        ret = self.client.get('/api/v1/chrom-sizes/?id=cs-hg19')

        assert(ret.status_code == 200)
        assert(len(ret.content) > 300)

        ret = self.client.get('/api/v1/chrom-sizes/?id=cs-hg19&type=json')

        data = json.loads(ret.content.decode('utf-8'))
        assert(ret.status_code == 200)
        assert('chr1' in data)

        ret = self.client.get(
            '/api/v1/chrom-sizes/?id=cs-hg19&type=json&cum=1'
        )

        data = json.loads(ret.content.decode('utf-8'))
        assert(ret.status_code == 200)
        assert('offset' in data['chr1'])

    def test_chromsizes_from_cooler(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        upload_file = open(
            'data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool',
            'rb'
        )
        self.chroms = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(
                upload_file.name, upload_file.read()
            ),
            filetype='cooler',
            datatype='matrix',
            coordSystem='hg19',
            owner=self.user1,
            uuid='cooler-dixon'
        )

        ret = self.client.get('/api/v1/chrom-sizes/?id=cooler-dixon')

        assert(ret.status_code == 200)
        assert(len(ret.content) > 300)

        ret = self.client.get('/api/v1/chrom-sizes/?id=cooler-dixon&type=json')

        data = json.loads(ret.content.decode('utf-8'))
        assert(ret.status_code == 200)
        assert('chr1' in data)

        ret = self.client.get(
            '/api/v1/chrom-sizes/?id=cooler-dixon&type=json&cum=1'
        )

        data = json.loads(ret.content.decode('utf-8'))
        assert(ret.status_code == 200)
        assert('offset' in data['chr1'])


class TilesetModelTest(dt.TestCase):
    def test_to_string(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        upload_file = open('data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool', 'rb')
        self.cooler = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name,
            upload_file.read()),
            filetype='cooler',
            owner=self.user1,
            uuid='x1x'
        )

        cooler_string = str(self.cooler)
        self.assertTrue(cooler_string.find("name") > 0)


class UnknownTilesetTypeTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool', 'rb')
        self.cooler = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='bar',
            datatype='foo',
            owner=self.user1,
            uuid='cli-huge-test'
        )

    def test_file_size(self):
        # make sure that the returned tiles are not overly large
        ret = self.client.get('/api/v1/tiles/?d=cli-huge-test.0.0.0')
        val = json.loads(ret.content.decode('utf-8'))

        # 32 bit:  349528
        # 16 bit:  174764

class TilesizeTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool', 'rb')
        self.cooler = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            owner=self.user1,
            uuid='x1x'
        )

    def test_file_size(self):
        # make sure that the returned tiles are not overly large
        ret = self.client.get('/api/v1/tiles/?d=x1x.0.0.0')
        val = json.loads(ret.content.decode('utf-8'))

        # 32 bit:  349528
        # 16 bit:  174764


class ViewConfTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_json_text = json.dumps({'hi': 'there'})

        self.viewconf = tm.ViewConf.objects.create(
                viewconf=upload_json_text, uuid='md')

    def test_viewconf(self):
        ret = self.client.get('/api/v1/viewconfs/?d=md')

        contents = json.loads(ret.content.decode('utf-8'))
        assert('hi' in contents)

    def test_viewconfs(self):
        ret = self.client.post(
            '/api/v1/viewconfs/',
            '{"uid": "123", "viewconf":{"hello": "sir"}}',
            content_type="application/json"
        )
        contents = json.loads(ret.content.decode('utf-8'))

        if hss.UPLOAD_ENABLED:
            self.assertIn('uid', contents)
            self.assertEqual(contents['uid'], '123')

            url = '/api/v1/viewconfs/?d=123'
            ret = self.client.get(url)

            contents = json.loads(ret.content.decode('utf-8'))

            assert('hello' in contents)
        else:
            self.assertEquals(ret.status_code, 403)

    def test_duplicate_uid_errors(self):
        ret1 = self.client.post(
            '/api/v1/viewconfs/',
            '{"uid": "dupe", "viewconf":{"try": "first"}}',
            content_type="application/json"
        )
        self.assertEqual(
            ret1.status_code,
            200 if hss.UPLOAD_ENABLED else 403
        )

        if hss.UPLOAD_ENABLED:
            # TODO: This will bubble up as a 500, when bad user input should
            # really be 4xx.
            ret = self.client.post(
                '/api/v1/viewconfs/',
                '{"uid": "dupe", "viewconf":{"try": "second"}}',
                content_type="application/json"
            )
            assert(ret.status_code == 400)

class PermissionsTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        self.user2 = dcam.User.objects.create_user(
            username='user2', password='pass'
        )

    def test_permissions(self):
        c1 = dt.Client()
        f = open('data/tiny.txt', 'rb')

        test_tileset = {
            'datafile': f,
            'filetype': 'hitile',
            'datatype': 'vector',
            'uid': 'bb',
            'private': 'True',
            'coordSystem': 'hg19',
            'name': "tr1"
        }

        response = c1.post(
            '/api/v1/tilesets/',
            test_tileset,
            format='multipart'
        )

        # user must be logged in to create objects
        assert(response.status_code == 403)
        f.close()

        c1.login(username='user1', password='pass')

        f = open('data/tiny.txt', 'rb')
        test_tileset = {
            'datafile': f,
            'filetype': 'hitile',
            'datatype': 'vector',
            'uid': 'cc',
            'private': 'True',
            'coordSystem': 'hg19',
            'name': "tr2"
        }

        response = c1.post(
            '/api/v1/tilesets/',
            test_tileset,
            format='multipart'
        )
        f.close()

        if hss.UPLOAD_ENABLED:
            # creating datasets is allowed if we're logged in
            assert(response.status_code == 201)

            ret = json.loads(response.content.decode('utf-8'))

            c2 = dt.Client()
            c2.login(username='user2', password='pass')

            # user2 should not be able to delete the tileset created by user1
            resp = c2.delete('/api/v1/tilesets/' + ret['uuid'] + "/")
            assert(resp.status_code == 403)

            # tileset should still be there
            resp = c1.get("/api/v1/tilesets/")
            assert(json.loads(resp.content.decode('utf-8'))['count'] == 1)

            # user1 should be able to delete his/her own tileset
            resp = c1.delete('/api/v1/tilesets/' + ret['uuid'] + "/")
            resp = c1.get("/api/v1/tilesets/")
            assert(resp.status_code == 200)

            assert(json.loads(resp.content.decode('utf-8'))['count'] == 0)

            c3 = dt.Client()
            resp = c3.get('/api/v1/tilesets/')

            # unauthenticated users should be able to see the (public) tileset
            # list
            assert(resp.status_code == 200)
        else:
            assert(response.status_code == 403)

    def test_filter(self):
        c1 = dt.Client()
        c1.login(username='user1', password='pass')
        f = open('data/tiny.txt', 'rb')

        test_tileset = {
            'datafile': f,
            'filetype': 'hitile',
            'datatype': 'vector',
            'uid': 'bb',
            'private': 'True',
            'coordSystem': 'hg19',
            'name': "tr1"
        }

        response = c1.post(
            '/api/v1/tilesets/',
            test_tileset,
            format='multipart'
        )

        f.close()
        f = open('data/tiny.txt', 'rb')

        test_tileset = {
            'datafile': f,
            'filetype': 'hitile',
            'datatype': 'vector',
            'uid': 'cc',
            'private': 'True',
            'coordSystem': 'hg19',
            'name': "tr2"
        }

        response = c1.post(
            '/api/v1/tilesets/',
            test_tileset,
            format='multipart'
        )
        f.close()
        assert(response is not None)

        ret = json.loads(c1.get('/api/v1/tilesets/').content.decode('utf-8'))
        assert(ret['count'] == 2)

        ret = json.loads(c1.get('/api/v1/tilesets/?ac=tr2').content.decode('utf-8'))
        assert(ret['count'] == 1)


class BigWigTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.bigWig', 'rb')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='bigwig',
            datatype='vector',
            owner=self.user1,
            coordSystem='hg19',
            coordSystem2='hg19',
            name="x",
            uuid='bw')

    def test_get_tileset_info(self):
        c1 = dt.Client()
        ret = json.loads(c1.get('/api/v1/tileset_info/?d=bw').content.decode('utf-8'))

    def test_get_tiles(self):
        '''
        Try to retrieve some tiles from this file
        '''
        c1 = dt.Client()
        c1.login(username='user1', password='pass')

        # make sure that the dataset has been added
        ret = json.loads(c1.get('/api/v1/tilesets/?d=bw').content.decode('utf-8'))
        assert(ret['count'] == 1)

        # try to retrieve the top level tile
        # ret = json.loads(c1.get('/api/v1/tiles/?d=bw.0.0').content.decode('utf-8'))
        # print("ret:", ret)

        # retrieve a tile that lies completely beyond the end of
        # the assembly
        ret = json.loads(c1.get('/api/v1/tiles/?d=bw.22.4194303').content.decode('utf-8'))


class CoolerTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool',
                           'rb')
        # x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name,
                upload_file.read()),
                filetype='cooler',
                datatype='matrix',
                owner=self.user1,
                coordSystem='hg19',
                coordSystem2='hg19',
                name="x",
                uuid='md')

        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name,
                upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            coordSystem='hg19',
            coordSystem2='hg19',
            name="t",
            uuid='rd')

        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            coordSystem='hg19',
            coordSystem2='hg19',
            name="Z",
            uuid='a')

        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            coordSystem='hg19',
            coordSystem2='hg19',
            name="v",
            uuid='sd1')

        upload_file = open('data/hic-resolutions.cool', 'rb')
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            coordSystem='x',
            coordSystem2='x',
            name="nuhr",
            uuid='nuhr')

    def test_order_by(self):
        '''
        Test to make sure that tilesets are correctly ordered when returned
        '''
        ret = self.client.get('/api/v1/tilesets/?o=uuid')
        contents = json.loads(ret.content.decode('utf-8'))

        uuids = [r['uuid'] for r in contents['results']]
        assert(uuids[0] < uuids[1])

        ret = self.client.get('/api/v1/tilesets/?o=uuid&r=1')
        contents = json.loads(ret.content.decode('utf-8'))

        uuids = [r['uuid'] for r in contents['results']]
        assert(uuids[0] > uuids[1])

        ret = self.client.get('/api/v1/tilesets/?o=name')
        contents = json.loads(ret.content.decode('utf-8'))

        names = [r['name'] for r in contents['results']]
        assert(names[0] < names[1])

        ret = self.client.get('/api/v1/tilesets/?o=name&r=1')
        contents = json.loads(ret.content.decode('utf-8'))

        names = [r['name'] for r in contents['results']]

        assert(names[0].lower() > names[1].lower())
        assert(names[0].lower() > names[-1].lower())


    def test_transforms(self):
        '''
        Try to get different transforms of the same tileset
        '''
        ret = self.client.get('/api/v1/tileset_info/?d=md')
        contents = json.loads(ret.content.decode('utf-8'))

        assert('transforms' in contents['md'])
        assert(contents['md']['transforms'][0]['name'] == 'ICE')

        ret = self.client.get('/api/v1/tiles/?d=md.0.0.0.default')
        contents = json.loads(ret.content.decode('utf-8'))

        ret = self.client.get('/api/v1/tiles/?d=md.0.0.0.none')
        contents1 = json.loads(ret.content.decode('utf-8'))

        # make sure that different normalization methods result
        # in different data being returned
        assert(contents['md.0.0.0.default']['dense'] != contents1['md.0.0.0.none']['dense'])

    def test_unbalanced(self):
        '''
        Try to get tiles from an unbalanced dataset
        '''
        upload_file = open('data/G15509.K-562.2_sampleDown.multires.cool', 'rb')
        tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            uuid='g1a')

        ret = self.client.get('/api/v1/tiles/?d=g1a.0.0.0')
        contents = json.loads(ret.content.decode('utf-8'))

        self.assertIn('g1a.0.0.0', contents)

    def test_tile_symmetry(self):
        '''
        Make sure that tiles are symmetric
        '''
        upload_file = open('data/Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool', 'rb')
        tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            uuid='aa')

        ret = self.client.get('/api/v1/tiles/?d=aa.0.0.0')


        contents = json.loads(ret.content.decode('utf-8'))

        import base64
        r = base64.decodestring(contents['aa.0.0.0']['dense'].encode('utf-8'))
        q = np.frombuffer(r, dtype=np.float16)

        q = q.reshape((256,256))


    def test_tile_boundary(self):
        '''
        Some recent changes made the tile boundaries appear darker than they should
        '''
        filename = 'data/Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool'
        tgt.make_mats('data/Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool')

        tileset_info = tgt.mats[filename][1]
        tileset_file = tgt.mats[filename][0]

        zoom_level = 3
        BINS_PER_TILE = 256

        hdf_for_resolution = tileset_file[str(zoom_level)]
        resolution = (tileset_info['max_width'] / 2**zoom_level) / BINS_PER_TILE

        tile = tt.make_tiles(hdf_for_resolution,
                resolution, 5,6)

        # this tile stretches down beyond the end of data and should thus contain no values
        assert(tile[(5,6)][-1] == 0.)


    def test_get_tileset_info(self):
        ret = self.client.get('/api/v1/tileset_info/?d=md')

        contents = json.loads(ret.content.decode('utf-8'))

        assert('md' in contents)
        assert('min_pos' in contents['md'])
        assert(contents['md']['coordSystem'] == 'hg19')

        ### test getting tileset info from files with non-powers of two resolutions
        ret = self.client.get('/api/v1/tileset_info/?d=nuhr')

        contents = json.loads(ret.content.decode('utf-8'))
        assert('nuhr' in contents)

    def test_get_multi_tiles(self):
        ret = self.client.get('/api/v1/tiles/?d=md.7.92.97&d=md.7.92.98&d=md.7.93.97&d=md.7.93.98&d=md.7.93.21')
        content = json.loads(ret.content.decode('utf-8'))

        assert('md.7.92.97' in content)
        assert('dense' in content['md.7.92.97'])

    def test_get_tiles(self):
        # this should fail in some manner because the tile is out of
        # bounds of the dataset

        ret = self.client.get('/api/v1/tiles/?d=nuhr.2.0.0')
        content = json.loads(ret.content.decode('utf-8'))

        assert('nuhr.2.0.0' in content)
        assert('dense' in content['nuhr.2.0.0'])
        return

        # this is to ensure that no exception is thrown
        ret = self.client.get('/api/v1/tiles/?d=nuhr.2.12.13')
        content = json.loads(ret.content.decode('utf-8'))

        assert('nuhr.2.0.0' in content)
        assert('dense' in content['nuhr.2.0.0'])

        return

        ret = self.client.get('/api/v1/tiles/?d=md.7.92.97')
        content = json.loads(ret.content.decode('utf-8'))

        assert('md.7.92.97' in content)
        assert('dense' in content['md.7.92.97'])

    def test_get_oob_tiles(self):
        # This test is obsolete
        # We don't necessarily need to return tiles that
        # are out of bounds. The client just handle the
        # fact that they aren't there
        ret = self.client.get('/api/v1/tiles/?d=md.6.63.63')
        content = json.loads(ret.content.decode('utf-8'))

        '''
        print("content:", content)
        assert('md.7.63.63' in content)
        assert('dense' in content['md.7.63.63'])
        '''

    def test_get_empty_tiles(self):
        # this test is here to ensure that the function call doesn't
        # throw an error because this tile has no data
        ret = self.client.get('/api/v1/tiles/?d=md.7.127.127')
        content = json.loads(ret.content.decode('utf-8'))

class SuggestionsTest(dt.TestCase):
    '''
    Test gene suggestions
    '''
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/gene_annotations.short.db', 'rb')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='beddb',
            datatype='gene-annotations',
            owner=self.user1,
            uuid='sut',
            coordSystem='hg19'
            )

    def test_suggest(self):
        # shouldn't be found and shouldn't raise an error
        ret = self.client.get('/api/v1/suggest/?d=xx&ac=r')

        ret = self.client.get('/api/v1/suggest/?d=sut&ac=r')
        suggestions = json.loads(ret.content.decode('utf-8'))

        self.assertGreater(len(suggestions), 0)
        self.assertGreater(suggestions[0]['score'], suggestions[1]['score'])

        ret = self.client.get('/api/v1/suggest/?d=sut&ac=r')
        suggestions = json.loads(ret.content.decode('utf-8'))

        self.assertGreater(len(suggestions), 0)
        self.assertGreater(suggestions[0]['score'], suggestions[1]['score'])


class FileUploadTest(dt.TestCase):
    '''
    Test file upload functionality
    '''
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

    def test_upload_file(self):
        c = dt.Client()
        c.login(username='user1', password='pass')

        f = open('data/tiny.txt', 'rb')

        response = c.post(
            '/api/v1/tilesets/',
            {
                'datafile': f,
                'filetype': 'hitile',
                'datatype': 'vector',
                'uid': 'bb',
                'private': 'True',
                'coordSystem': 'hg19'
            },
            format='multipart'
        )

        if hss.UPLOAD_ENABLED:
            self.assertEqual(rfs.HTTP_201_CREATED, response.status_code)

            response = c.get('/api/v1/tilesets/')

            obj = tm.Tileset.objects.get(uuid='bb')

            # make sure the file was actually created
            self.assertTrue(op.exists, obj.datafile.url)
        else:
            self.assertEqual(403, response.status_code)


class GetterTest(dt.TestCase):
    def test_get_info(self):
        filepath = 'data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool'
        info = cch.get_info(filepath)

        self.assertEqual(info['max_zoom'], 4)
        self.assertEqual(info['max_width'], 1000000 * 2 ** 12)


class Bed2DDBTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/arrowhead_domains_short.txt.multires.db', 'rb')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='bed2ddb',
            datatype='arrowhead-domains',
            owner=self.user1,
            uuid='ahd')


        upload_file1 = open('data/Rao_RepH_GM12878_InsulationScore.txt.multires.db', 'rb')

        self.tileset1 = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file1.name, upload_file1.read()),
            filetype='bed2ddb',
            datatype='2d-rectangle-domains',
            owner=self.user1,
            uuid='ahe')

    def test_uids_by_filename(self):
        ret = self.client.get('/api/v1/uids_by_filename/?d=Rao_RepH_GM12878_InsulationScore.txt')

        contents = json.loads(ret.content.decode('utf-8'))

        assert(contents["count"] == 1)

        ret = self.client.get('/api/v1/uids_by_filename/?d=xRao_RepH_GM12878_InsulationScore')

        contents = json.loads(ret.content.decode('utf-8'))

        assert(contents["count"] == 0)

    def test_get_tile(self):
        tile_id="{uuid}.{z}.{x}.{y}".format(uuid=self.tileset.uuid, z=0, x=0, y=0)
        returned_text = self.client.get('/api/v1/tiles/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content.decode('utf-8'))

        ret = self.client.get('/api/v1/tiles/?d={}.0.0.0'.format(self.tileset1.uuid))
        assert(ret.status_code == 200)

        contents = json.loads(ret.content.decode('utf-8'))

    def test_get_tiles(self):
        tile_id00="{uuid}.{z}.{x}.{y}".format(uuid=self.tileset.uuid, z=0, x=0, y=0)
        tile_id01="{uuid}.{z}.{x}.{y}".format(uuid=self.tileset.uuid, z=0, x=0, y=1)
        tile_id10="{uuid}.{z}.{x}.{y}".format(uuid=self.tileset.uuid, z=0, x=1, y=0)
        returned_text = self.client.get('/api/v1/tiles/?d={}&d={}&d={}'.format(tile_id00, tile_id01, tile_id10))
        returned = json.loads(returned_text.content.decode('utf-8'))

        ret = self.client.get('/api/v1/tiles/?d={}.0.0.0'.format(self.tileset1.uuid))
        assert(ret.status_code == 200)

        contents = json.loads(ret.content.decode('utf-8'))

    def test_get_info(self):
        ret = self.client.get('/api/v1/tileset_info/?d={}'.format(self.tileset1.uuid))

        assert(ret.status_code == 200)


class BedDBTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/gene_annotations.short.db', 'rb')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='beddb',
            datatype='gene-annotations',
            owner=self.user1,
            uuid='bdb')

    def test_get_tile(self):
        tile_id="{uuid}.{z}.{x}".format(uuid=self.tileset.uuid, z=0, x=0)
        returned_text = self.client.get('/api/v1/tiles/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content.decode('utf-8'))

        for x in returned['bdb.0.0']:
            assert('uid' in x)
            assert('importance' in x)
            assert('fields' in x)

    def test_get_tiles(self):
        tile_id="{uuid}.{z}.{x}".format(uuid=self.tileset.uuid, z=1, x=0)
        tile_id1="{uuid}.{z}.{x}".format(uuid=self.tileset.uuid, z=1, x=1)
        returned_text = self.client.get('/api/v1/tiles/?d={tile_id}&d={tile_id1}'.format(tile_id=tile_id, tile_id1=tile_id1))
        returned = json.loads(returned_text.content.decode('utf-8'))

        assert(len(returned[tile_id]) > 0)
        assert(len(returned[tile_id1]) > 0)

        for x in returned[tile_id]:
            assert('uid' in x)
            assert('importance' in x)
            assert('fields' in x)

        for x in returned[tile_id1]:
            assert('uid' in x)
            assert('importance' in x)
            assert('fields' in x)

class HiBedTest(dt.TestCase):
    '''
    Test retrieving interval data (hibed)
    '''
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/cnv_short.hibed', 'rb')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='hibed',
            datatype='stacked-interval',
            coordSystem='hg19',
            owner=self.user1,
            uuid='hbt')


    def test_hibed_get_tile(self):
        tile_id="{uuid}.{z}.{x}".format(uuid=self.tileset.uuid, z=0, x=0)
        returned_text = self.client.get('/api/v1/tiles/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content.decode('utf-8'))

        self.assertTrue('discrete' in returned[tile_id])

    def test_hibed_get_tileset_info(self):
        tile_id="{uuid}".format(uuid=self.tileset.uuid)
        returned_text = self.client.get('/api/v1/tileset_info/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content.decode('utf-8'))

        self.assertTrue('tile_size' in returned[tile_id])
        self.assertEqual(returned[tile_id]['coordSystem'], 'hg19')


class TilesetsViewSetTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        self.user2 = dcam.User.objects.create_user(
            username='user2', password='pass'
        )

        upload_file = open('data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool', 'rb')
        self.cooler = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            owner=self.user1
        )

        upload_file=open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'rb')
        self.hitile = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='hitile',
            owner=self.user1
        )

    def tearDown(self):
        tm.Tileset.objects.all().delete()

    def check_tile(self, z, x, y):
        returned = json.loads(
            self.client.get(
                '/api/v1/tiles/?d={uuid}.{z}.{x}.{y}'.format(
                    uuid=self.cooler.uuid, x=x, y=y, z=z
                )
            ).content.decode('utf-8')
        )

        r = base64.decodestring(returned[list(returned.keys())[0]]['dense'].encode('utf-8'))
        q = np.frombuffer(r, dtype=np.float16)

        with h5py.File(self.cooler.datafile.url) as f:
            tileset_info = cch.get_info(self.cooler.datafile.url)
            tileset_file = f

            mat = [tileset_file, tileset_info]

            zoom_level = z
            BINS_PER_TILE = 256

            hdf_for_resolution = tileset_file[str(zoom_level)]
            resolution = (tileset_info['max_width'] / 2**zoom_level) / BINS_PER_TILE

            t = tt.make_tiles(hdf_for_resolution, resolution, x, y)[(x,y)]

            # test the base64 encoding
            self.assertTrue(np.isclose(sum(q), sum(t), rtol=1e-3))

            # make sure we're returning actual data
            self.assertGreater(sum(q), 0)

    def test_create_with_anonymous_user(self):
        """
        Don't allow the creation of datasets by anonymouse users.
        """
        with self.assertRaises(ValueError):
            upload_file =open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'rb')
            tm.Tileset.objects.create(
                datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
                filetype='hitile',
                owner=dcam.AnonymousUser()
            )

    def test_post_dataset(self):
        c = dt.Client()
        c.login(username='user1', password='pass')
        f = open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'rb')
        ret = c.post(
            '/api/v1/tilesets/',
            {
                'datafile': f,
                'filetype': 'hitile',
                'private': 'True',
                'coordSystem': 'hg19'
            }
            ,
            format='multipart'
        )
        f.close()
        ret_obj = json.loads(ret.content.decode('utf-8'))

        if hss.UPLOAD_ENABLED:
            t = tm.Tileset.objects.get(uuid=ret_obj['uuid'])

            # this object should be private because we were logged in and
            # requested it to be private
            self.assertTrue(t.private)

            c.login(username='user2', password='pass')
            ret = c.get('/api/v1/tileset_info/?d={uuid}'.format(
                uuid=ret_obj['uuid'])
            )

            # user2 should not be able to get information about this dataset
            ts_info = json.loads(ret.content.decode('utf-8'))
            self.assertTrue('error' in ts_info[ret_obj['uuid']])

            c.login(username='user1', password='pass')
            ret = c.get('/api/v1/tileset_info/?d={uuid}'.format(
                uuid=ret_obj['uuid'])
            )

            # user1 should be able to access it
            ts_info = json.loads(ret.content.decode('utf-8'))
            self.assertFalse('error' in ts_info[ret_obj['uuid']])
            self.assertEqual(ts_info[ret_obj['uuid']]['coordSystem'], 'hg19')

            # upload a new dataset as user1
            ret = c.post(
                '/api/v1/tilesets/',
                {
                    'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'rb'),
                    'filetype': 'hitile',
                    'private': 'False',
                    'coordSystem': 'hg19'

                },
                format='multipart'
            )
            ret_obj = json.loads(ret.content.decode('utf-8'))

            # since the previously uploaded dataset is not private, we should be
            # able to access it as user2
            c.login(username='user2', password='pass')
            ret = c.get('/api/v1/tileset_info/?d={uuid}'.format(uuid=ret_obj['uuid']))
            ts_info = json.loads(ret.content.decode('utf-8'))

            self.assertFalse('error' in ts_info[ret_obj['uuid']])
        else:
            self.assertEquals(ret.status_code, 403)

    def test_create_private_tileset(self):
        """Test to make sure that when we create a private dataset, we can only
        access it if we're logged in as the proper user
        """

        upload_file =open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'rb')
        private_obj = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='hitile',
            private=True,
            owner=self.user1
        )

        c = dt.Client()
        c.login(username='user1', password='pass')
        returned = json.loads(
            self.client.get(
                '/api/v1/tileset_info/?d={uuid}'.format(uuid=private_obj.uuid)
            ).content.decode('utf-8')
        )

    def test_get_top_tile(self):
        """
        Get the top level tile
        """

        self.check_tile(0, 0, 0)
        self.check_tile(4, 0, 0)

    def test_get_many_tiles(self):
        """Test to make sure that requesting multiple tiles returns a JSON
        object with an entry for each tile.
        """

        returned = json.loads(
            self.client.get(
                '/api/v1/tiles/?d={uuid}.1.0.0&d={uuid}.1.0.1'.format(
                    uuid=self.cooler.uuid
                )
            ).content.decode('utf-8')
        )

        self.assertTrue('{uuid}.1.0.0'.format(
            uuid=self.cooler.uuid) in returned.keys()
        )
        self.assertTrue('{uuid}.1.0.1'.format(
            uuid=self.cooler.uuid) in returned.keys()
        )

    def test_get_same_tiles(self):
        """
        Test to make sure that we return tileset info for 1D tracks
        """
        returned = json.loads(
            self.client.get(
                '/api/v1/tiles/?d={uuid}.1.0.0&d={uuid}.1.0.0'.format(
                    uuid=self.cooler.uuid
                )
            ).content.decode('utf-8')
        )

        self.assertEquals(len(returned.keys()), 1)

        pass

    def test_get_nonexistent_tile(self):
        """ Test to make sure we don't throw an error when requesting a
        non-existent tile. It just needs to be missing from the return array.
        """

        returned = json.loads(
            self.client.get(
                '/api/v1/tiles/?d={uuid}.1.5.5'.format(uuid=self.cooler.uuid)
            ).content.decode('utf-8')
        )

        self.assertTrue(
            '{uuid}.1.5.5'.format(
                uuid=self.cooler.uuid
            ) not in returned.keys()
        )

        returned = json.loads(
            self.client.get(
                '/api/v1/tiles/?d={uuid}.20.5.5'.format(uuid=self.cooler.uuid)
            ).content.decode('utf-8')
        )

        self.assertTrue(
            '{uuid}.1.5.5'.format(
                uuid=self.cooler.uuid
            ) not in returned.keys()
        )

    def test_get_hitile_tileset_info(self):
        returned = json.loads(
            self.client.get(
                '/api/v1/tileset_info/?d={uuid}'.format(uuid=self.hitile.uuid)
            ).content.decode('utf-8')
        )

        uuid = "{uuid}".format(uuid=self.hitile.uuid)

        self.assertTrue(
            "{uuid}".format(uuid=self.hitile.uuid) in returned.keys()
        )
        self.assertEqual(returned[uuid][u'max_zoom'], 22)
        self.assertEqual(returned[uuid][u'max_width'], 2 ** 32)

        self.assertTrue(u'name' in returned[uuid])

    def test_get_cooler_tileset_info(self):
        returned = json.loads(
            self.client.get(
                '/api/v1/tileset_info/?d={uuid}'.format(uuid=self.cooler.uuid)
            ).content.decode('utf-8')
        )

        uuid = "{uuid}".format(uuid=self.cooler.uuid)
        self.assertTrue(u'name' in returned[uuid])


    def test_get_hitile_tile(self):
        returned = json.loads(
            self.client.get(
                '/api/v1/tiles/?d={uuid}.0.0'.format(uuid=self.hitile.uuid)
            ).content.decode('utf-8')
        )

        self.assertTrue("{uuid}.0.0".format(uuid=self.hitile.uuid) in returned)
        pass

    def test_list_tilesets(self):
        c = dt.Client()
        c.login(username='user1', password='pass')
        ret = c.post(
            '/api/v1/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                'filetype': 'hitile',
                'private': 'True',
                'name': 'one',
                'coordSystem': 'hg19'
            }
        )
        ret = c.post(
            '/api/v1/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                'filetype': 'hitile',
                'private': 'True',
                'name': 'tone',
                'coordSystem': 'hg19'
            }
        )
        ret = c.post(
            '/api/v1/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                'filetype': 'cooler',
                'private': 'True',
                'name': 'tax',
                'coordSystem': 'hg19'
            }
        )
        ret = c.get('/api/v1/tilesets/?ac=ne')
        self.assertEquals(ret.status_code, 200)

        ret = json.loads(ret.content.decode('utf-8'))

        if hss.UPLOAD_ENABLED:
            count1 = ret['count']
            self.assertTrue(count1 > 0)

            names = set([ts['name'] for ts in ret['results']])

            self.assertTrue(u'one' in names)
            self.assertFalse(u'tax' in names)

            c.logout()
            # all tilesets should be private
            ret = json.loads(c.get('/api/v1/tilesets/?ac=ne').content.decode('utf-8'))
            self.assertEquals(ret['count'], 0)

            ret = json.loads(c.get('/api/v1/tilesets/?ac=ne&t=cooler').content.decode('utf-8'))
            count1 = ret['count']
            self.assertTrue(count1 == 0)

            c.login(username='user2', password='pass')
            ret = json.loads(c.get('/api/v1/tilesets/?q=ne').content.decode('utf-8'))

            names = set([ts['name'] for ts in ret['results']])
            self.assertFalse(u'one' in names)

            ret = c.post(
                '/api/v1/tilesets/',
                {
                    'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                    'filetype': 'xxxyx',
                    'datatype': 'vector',
                    'private': 'True',
                }
            )

            # not coordSystem field
            assert(ret.status_code == rfs.HTTP_400_BAD_REQUEST)
            ret = json.loads(c.get('/api/v1/tilesets/?t=xxxyx').content.decode('utf-8'))

            assert(ret['count'] == 0)

            ret = c.post(
                '/api/v1/tilesets/',
                {
                    'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                    'filetype': 'xxxyx',
                    'datatype': 'vector',
                    'private': 'True',
                    'coordSystem': 'hg19',
                }
            )

            ret = json.loads(c.get('/api/v1/tilesets/?t=xxxyx').content.decode('utf-8'))
            self.assertEqual(ret['count'], 1)
        else:
            self.assertEquals(ret['count'], 0)

    def test_add_with_uid(self):
        self.client.login(username='user1', password='pass')
        ret = self.client.post(
            '/api/v1/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                'filetype': 'a',
                'datatype': 'vector',
                'private': 'True',
                'uid': 'aaaaaaaaaaaaaaaaaaaaaa',
                'coordSystem': 'hg19'
            }
        )

        ret = json.loads(self.client.get('/api/v1/tilesets/').content.decode('utf-8'))

        if hss.UPLOAD_ENABLED:
            # the two default datasets plus the added one
            self.assertEquals(ret['count'], 3)

            # try to add one more dataset with a specified uid
            ret = json.loads(
                self.client.post(
                    '/api/v1/tilesets/',
                    {
                        'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                        'filetype': 'a',
                        'datatype': 'vector',
                        'private': 'True',
                        'uid': 'aaaaaaaaaaaaaaaaaaaaaa',
                        'coordSystem': 'hg19'
                    }
                ).content.decode('utf-8')
            )

            # there should be a return value explaining that we can't add a tileset
            # which has an existing uuid
            self.assertTrue('detail' in ret)

            ret = json.loads(self.client.get('/api/v1/tilesets/').content.decode('utf-8'))
            self.assertEquals(ret['count'], 3)
        else:
            self.assertEquals(ret['count'], 2)

    def test_list_by_datatype(self):
        self.client.login(username='user1', password='pass')
        ret = self.client.post(
            '/api/v1/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                'filetype': 'a',
                'datatype': '1',
                'private': 'True',
                'coordSystem': 'hg19',
                'uid': 'aaaaaaaaaaaaaaaaaaaaaa'
            }
        )

        ret = self.client.post(
            '/api/v1/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','rb'),
                'filetype': 'a',
                'datatype': '2',
                'private': 'True',
                'coordSystem': 'hg19',
                'uid': 'bb'
            }
        )

        ret = json.loads(self.client.get('/api/v1/tilesets/?dt=1').content.decode('utf-8'))
        self.assertEqual(ret['count'], 1 if hss.UPLOAD_ENABLED else 0)

        ret = json.loads(self.client.get('/api/v1/tilesets/?dt=2').content.decode('utf-8'))
        self.assertEqual(ret['count'], 1 if hss.UPLOAD_ENABLED else 0)

        ret = json.loads(self.client.get('/api/v1/tilesets/?dt=1&dt=2').content.decode('utf-8'))
        self.assertEqual(ret['count'], 2 if hss.UPLOAD_ENABLED else 0)

    def test_get_nonexistant_tileset_info(self):
        ret = json.loads(self.client.get('/api/v1/tileset_info/?d=x1x').content.decode('utf-8'))

        # make sure above doesn't raise an error


# Create your tests here.
