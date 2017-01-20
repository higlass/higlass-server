from __future__ import print_function

import django.core.files as dcf
import django.core.files.uploadedfile as dcfu
import django.contrib.auth.models as dcam

import base64
import django.test as dt
import h5py
import json
import os.path as op
import numpy as np
import getter
import rest_framework.status as rfs
import tiles

import tilesets.models as tm

class ViewConfTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_json_text = json.dumps({'hi': 'there'})

        self.viewconf = tm.ViewConf.objects.create(
                viewconf=upload_json_text, uuid='md')

    def test_viewconf(self):
        ret = self.client.get('/viewconfs/?d=md')

        contents = json.loads(ret.content)
        assert('hi' in contents)

    def test_viewconfs(self):
        ret = self.client.post('/viewconfs/',
                {'xx': '{"hello": "sir"}'})

        assert(ret.status_code == rfs.HTTP_400_BAD_REQUEST)
        contents = json.loads(ret.content)
        assert('error' in contents)

        ret = self.client.post('/viewconfs/',
                {'viewconf': '{"hello": "sir"}'})
        contents = json.loads(ret.content)
        assert('uid' in contents)

        url = '/viewconfs/?d=' + contents['uid']
        ret = self.client.get(url)

        contents = json.loads(ret.content)

        assert('hello' in contents)
        


class CoolerTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/Dixon2012-J1-NcoI-R1-filtered.100kb.multires.cool', 'r')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            datatype='matrix',
            owner=self.user1,
            uuid='md')

    def test_get_tileset_info(self):
        ret = self.client.get('/tileset_info/?d=md')

        contents = json.loads(ret.content)

        assert('md' in contents)
        assert('min_pos' in contents['md'])

    def test_get_tiles(self):
        ret = self.client.get('/tiles/?d=md.7.92.97')
        content = json.loads(ret.content)

        assert('md.7.92.97' in content)
        assert('dense' in content['md.7.92.97'])


class SuggestionsTest(dt.TestCase):
    '''
    Test gene suggestions
    '''
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/gene_annotations.short.db', 'r')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='beddb',
            datatype='gene-annotations',
            owner=self.user1,
            uuid='hhb',
            coordSystem='hg19'
            )

    def test_suggest(self):
        # shouldn't be found and shouldn't raise an error
        ret = self.client.get('/suggest/?d=xx&ac=r')

        ret = self.client.get('/suggest/?d=hhb&ac=r')
        suggestions = json.loads(ret.content)

        self.assertGreater(len(suggestions), 0)
        self.assertGreater(suggestions[0]['score'], suggestions[1]['score'])

        ret = self.client.get('/suggest/?d=hhb&ac=r')
        suggestions = json.loads(ret.content)
        
        self.assertGreater(len(suggestions), 0)
        self.assertGreater(suggestions[0]['score'], suggestions[1]['score'])


class FileUploadTest(dt.TestCase):
    '''
    Test file upload functionality
    '''
    def test_upload_file(self):
        c = dt.Client()
        f = open( 'data/tiny.txt', 'r')

        response = c.post(
            '/tilesets/',
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

        self.assertEqual(rfs.HTTP_201_CREATED, response.status_code)

        response = c.get('/tilesets/')

        obj = tm.Tileset.objects.get(uuid='bb')

        # make sure the file was actually created
        self.assertTrue(op.exists, obj.datafile.url)

class GetterTest(dt.TestCase):
    def test_get_info(self):
        filepath = 'data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool'
        info = getter.get_info(filepath)

        self.assertEqual(info['max_zoom'], 4)
        self.assertEqual(info['max_width'], 1000000 * 2 ** 12)

class Bed2DDBTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/arrowhead_domains_short.txt.multires.db', 'r')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='bed2ddb',
            datatype='arrowhead-domains',
            owner=self.user1,
            uuid='hhb')

    def test_get_tile(self):
        tile_id="{uuid}.{z}.{x}.{y}".format(uuid=self.tileset.uuid, z=0, x=0, y=0)
        returned_text = self.client.get('/tiles/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content)

class BedDBTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/gene_annotations.short.db', 'r')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='beddb',
            datatype='gene-annotations',
            owner=self.user1,
            uuid='hhb')

    def test_get_tile(self):
        tile_id="{uuid}.{z}.{x}".format(uuid=self.tileset.uuid, z=0, x=0)
        returned_text = self.client.get('/tiles/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content)

class HiBedTest(dt.TestCase):
    '''
    Test retrieving interval data (hibed)
    '''
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_file = open('data/cnv_short.hibed', 'r')
        #x = upload_file.read()
        self.tileset = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='hibed',
            datatype='stacked-interval',
            owner=self.user1,
            uuid='hhb')


    def test_hibed_get_tile(self):
        tile_id="{uuid}.{z}.{x}".format(uuid=self.tileset.uuid, z=0, x=0)
        returned_text = self.client.get('/tiles/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content)

        self.assertTrue('discrete' in returned[tile_id])

    def test_hibed_get_tileset_info(self):
        tile_id="{uuid}".format(uuid=self.tileset.uuid)
        returned_text = self.client.get('/tileset_info/?d={tile_id}'.format(tile_id=tile_id))
        returned = json.loads(returned_text.content)

        self.assertTrue('tile_size' in returned[tile_id])

class TilesetsViewSetTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        self.user2 = dcam.User.objects.create_user(
            username='user2', password='pass'
        )

        upload_file = open('data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool', 'r')
        self.cooler = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='cooler',
            owner=self.user1
        )

        upload_file=open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'r')
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
                '/tiles/?d={uuid}.{z}.{x}.{y}'.format(
                    uuid=self.cooler.uuid, x=x, y=y, z=z
                )
            ).content
        )

        r = base64.decodestring(returned[returned.keys()[0]]['dense'])
        q = np.frombuffer(r, dtype=np.float32)

        with h5py.File(self.cooler.datafile.url) as f:

            mat = [f, getter.get_info(self.cooler.datafile.url)]
            t = tiles.make_tile(z, x, y, mat)

            # test the base64 encoding
            self.assertTrue(np.isclose(sum(q), sum(t)))

            # make sure we're returning actual data
            self.assertGreater(sum(q), 0)

    def test_create_with_anonymous_user(self):
        """
        Don't allow the creation of datasets by anonymouse users.
        """
        with self.assertRaises(ValueError):
            upload_file =open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'r') 
            tm.Tileset.objects.create(
                datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
                filetype='hitile',
                owner=dcam.AnonymousUser()
            )

    def test_post_dataset(self):
        ret = self.client.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'r'),
                'filetype': 'hitile',
                'private': 'True',
                'coordSystem': 'hg19'
            },
            format='multipart'
        )
        ret_obj = json.loads(ret.content)

        # since we posted this object as anonymous, we expect it not be private
        t = tm.Tileset.objects.get(uuid=ret_obj['uuid'])
        self.assertFalse(t.private)

        c = dt.Client()
        c.login(username='user1', password='pass')
        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'r'),
                'filetype': 'hitile',
                'private': 'True',
                'coordSystem': 'hg19'
            }
            ,
            format='multipart'
        )
        ret_obj = json.loads(ret.content)
        t = tm.Tileset.objects.get(uuid=ret_obj['uuid'])

        # this object should be private because we were logged in and requested
        # it to be private
        self.assertTrue(t.private)

        c.login(username='user2', password='pass')
        ret = c.get('/tileset_info/?d={uuid}'.format(uuid=ret_obj['uuid']))

        # user2 should not be able to get information about this dataset
        ts_info = json.loads(ret.content)
        self.assertTrue('error' in ts_info[ret_obj['uuid']])

        c.login(username='user1', password='pass')
        ret = c.get('/tileset_info/?d={uuid}'.format(uuid=ret_obj['uuid']))

        # user1 should be able to access it
        ts_info = json.loads(ret.content)
        self.assertFalse('error' in ts_info[ret_obj['uuid']])

        # upload a new dataset as user1
        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'r'),
                'filetype': 'hitile',
                'private': 'False',
                'coordSystem': 'hg19'

            },
            format='multipart'
        )
        ret_obj = json.loads(ret.content)

        # since the previously uploaded dataset is not private, we should be
        # able to access it as user2
        c.login(username='user2', password='pass')
        ret = c.get('/tileset_info/?d={uuid}'.format(uuid=ret_obj['uuid']))
        ts_info = json.loads(ret.content)

        self.assertFalse('error' in ts_info[ret_obj['uuid']])

    def test_create_private_tileset(self):
        """Test to make sure that when we create a private dataset, we can only
        access it if we're logged in as the proper user
        """

        upload_file =open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile', 'r') 
        private_obj = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            filetype='hitile',
            private=True,
            owner=self.user1
        )

        c = dt.Client()
        c.login(username='user1', password='pass')
        returned = json.loads(
            self.client.get('/tileset_info/?d={uuid}'.format(uuid=private_obj.uuid)).content
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
                '/tiles/?d={uuid}.1.0.0&d={uuid}.1.0.1'.format(
                    uuid=self.cooler.uuid
                )
            ).content
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
                '/tiles/?d={uuid}.1.0.0&d={uuid}.1.0.0'.format(
                    uuid=self.cooler.uuid
                )
            ).content
        )

        self.assertEquals(len(returned.keys()), 1)

        pass

    def test_get_nonexistent_tile(self):
        """ Test to make sure we don't throw an error when requesting a
        non-existent tile. It just needs to be missing from the return array.
        """

        returned = json.loads(
            self.client.get(
                '/tiles/?d={uuid}.1.5.5'.format(uuid=self.cooler.uuid)
            ).content
        )

        self.assertTrue(
            '{uuid}.1.5.5'.format(
                uuid=self.cooler.uuid
            ) not in returned.keys()
        )

        returned = json.loads(
            self.client.get(
                '/tiles/?d={uuid}.20.5.5'.format(uuid=self.cooler.uuid)
            ).content
        )

        self.assertTrue(
            '{uuid}.1.5.5'.format(
                uuid=self.cooler.uuid
            ) not in returned.keys()
        )

    def test_get_hitile_tileset_info(self):
        returned = json.loads(
            self.client.get(
                '/tileset_info/?d={uuid}'.format(uuid=self.hitile.uuid)
            ).content
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
                '/tileset_info/?d={uuid}'.format(uuid=self.cooler.uuid)
            ).content
        )

        uuid = "{uuid}".format(uuid=self.cooler.uuid)
        self.assertTrue(u'name' in returned[uuid])


    def test_get_hitile_tile(self):
        returned = json.loads(
            self.client.get(
                '/tiles/?d={uuid}.0.0'.format(uuid=self.hitile.uuid)
            ).content
        )

        self.assertTrue("{uuid}.0.0".format(uuid=self.hitile.uuid) in returned)
        pass

    def test_list_tilesets(self):
        c = dt.Client()
        c.login(username='user1', password='pass')
        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'hitile',
                'private': 'True',
                'name': 'one',
                'coordSystem': 'hg19'
            }
        )
        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'hitile',
                'private': 'True',
                'name': 'tone',
                'coordSystem': 'hg19'
            }
        )
        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'cooler',
                'private': 'True',
                'name': 'tax',
                'coordSystem': 'hg19'
            }
        )
        ret = json.loads(c.get('/tilesets/?ac=ne').content)
        count1 = ret['count']
        self.assertTrue(count1 > 0)

        names = set([ts['name'] for ts in ret['results']])

        self.assertTrue(u'one' in names)
        self.assertFalse(u'tax' in names)

        c.logout()
        # all tilesets should be private
        ret = json.loads(c.get('/tilesets/?ac=ne').content)
        self.assertEquals(ret['count'], 0)

        ret = json.loads(c.get('/tilesets/?ac=ne&t=cooler').content)
        count1 = ret['count']
        self.assertTrue(count1 == 0)

        c.login(username='user2', password='pass')
        ret = json.loads(c.get('/tilesets/?q=ne').content)

        names = set([ts['name'] for ts in ret['results']])
        self.assertFalse(u'one' in names)

        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'xxxyx',
                'datatype': 'vector',
                'private': 'True',
            }
        )

        # not coordSystem field
        assert(ret.status_code == rfs.HTTP_400_BAD_REQUEST)
        ret = json.loads(c.get('/tilesets/?t=xxxyx').content)

        assert(ret['count'] == 0)

        ret = c.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'xxxyx',
                'datatype': 'vector',
                'private': 'True',
                'coordSystem': 'hg19',
            }
        )

        ret = json.loads(c.get('/tilesets/?t=xxxyx').content)
        self.assertEqual(ret['count'], 1)

    def test_add_with_uid(self):
        ret = self.client.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'a',
                'datatype': 'vector',
                'private': 'True',
                'uid': 'aaaaaaaaaaaaaaaaaaaaaa',
                'coordSystem': 'hg19'
            }
        )

        ret = json.loads(self.client.get('/tilesets/').content)

        # the two default datasets plus the added one
        self.assertEquals(ret['count'], 3)

        # try to add one more dataset with a specified uid
        ret = json.loads(
            self.client.post(
                '/tilesets/',
                {
                    'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                    'filetype': 'a',
                    'datatype': 'vector',
                    'private': 'True',
                    'uid': 'aaaaaaaaaaaaaaaaaaaaaa',
                    'coordSystem': 'hg19'
                }
            ).content
        )

        # there should be a return value explaining that we can't add a tileset
        # which has an existing uuid
        self.assertTrue('detail' in ret)

        ret = json.loads(self.client.get('/tilesets/').content)
        self.assertEquals(ret['count'], 3)

    def test_list_by_datatype(self):
        ret = self.client.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'a',
                'datatype': '1',
                'private': 'True',
                'coordSystem': 'hg19',
                'uid': 'aaaaaaaaaaaaaaaaaaaaaa'
            }
        )

        ret = self.client.post(
            '/tilesets/',
            {
                'datafile': open('data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile','r'),
                'filetype': 'a',
                'datatype': '2',
                'private': 'True',
                'coordSystem': 'hg19',
                'uid': 'bb'
            }
        )


        ret = json.loads(self.client.get('/tilesets/?dt=1').content)
        self.assertEqual(ret['count'], 1)

        ret = json.loads(self.client.get('/tilesets/?dt=2').content)
        self.assertEqual(ret['count'], 1)

        ret = json.loads(self.client.get('/tilesets/?dt=1&dt=2').content)
        self.assertEqual(ret['count'], 2)

    def test_get_nonexistant_tileset_info(self):
        ret = json.loads(self.client.get('/tileset_info/?d=x1x').content)

        # make sure above doesn't raise an error 


# Create your tests here.
