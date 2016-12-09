from django.test import TestCase

from tilesets.models import Tileset
from django.urls import reverse

import django.contrib.auth.models as dcam

import base64
import h5py
import json
import numpy as np
import getter as hgg
import tiles

class GetterTest(TestCase):
    def test_getInfo(self):
        filepath =  'data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool'
        info = hgg.getInfo(filepath)

        self.assertEqual(info['max_zoom'], 4)
        self.assertEqual(info['max_width'], 1000000 * 2 ** 12)


class TilesetsViewSetTest(TestCase):
    def setUp(self):
        self.user = dcam.User.objects.create_user(username='public', email='user@host.com', password='')

        self.tileset = Tileset.objects.create(processed_file='data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool',
                    file_type='cooler', owner=self.user)
        self.hitile = Tileset.objects.create(processed_file='data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile',
                    file_type='hitile', owner=self.user)

    def check_tile(self, z,x,y):
        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.{z}.{x}.{y}'.format(uuid=self.tileset.uuid,x=x,y=y,z=z)).content)

        r = base64.decodestring(returned[returned.keys()[0]]['dense'])
        q = np.frombuffer(r, dtype=np.float32)

        with h5py.File(self.tileset.processed_file) as f:

            mat = [f, hgg.getInfo(self.tileset.processed_file)]
            t = tiles.makeTile(z,x,y, mat)

            #print("sum", sum(q))
            #print("sum", sum(t))
            # test the base64 encoding
            self.assertTrue(np.isclose(sum(q), sum(t)))

            # make sure we're returning actual data
            self.assertGreater(sum(q), 0)

    def test_create_with_anonymous_user(self):
        '''
        Don't allow the creation of datasets by anonymouse users.
        '''
        #with self.assertRaises(ValueError): 
        Tileset.objects.create(processed_file='data/wgEncodeCaltechRnaSeqHuvecR1x75dTh1014IlnaPlusSignalRep2.hitile',
                                         file_type='hitile', 
                                         owner=dcam.AnonymousUser())

    def test_get_top_tile(self):
        '''
        Get the top level tile
        '''

        self.check_tile(0,0,0)
        self.check_tile(4,0,0)

    def test_get_many_tiles(self):
        '''
        Test to make sure that requesting multiple tiles returns a JSON object with an entry for
        each tile.
        '''

        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.1.0.0&d={uuid}.1.0.1'.format(uuid=self.tileset.uuid)).content)

        self.assertTrue('{uuid}.1.0.0'.format(uuid=self.tileset.uuid) in returned.keys())
        self.assertTrue('{uuid}.1.0.1'.format(uuid=self.tileset.uuid) in returned.keys())

    def test_get_same_tiles(self):
        '''
        Test to make sure that we return tileset info for 1D tracks
        '''
        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.1.0.0&d={uuid}.1.0.0'.format(uuid=self.tileset.uuid)).content)

        self.assertEquals(len(returned.keys()), 1)

        pass


    def test_get_nonexistent_tile(self):
        '''
        Test to make sure we don't throw an error when requesting a non-existent tile. It just
        needs to be missing from the return array.
        '''
        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.1.5.5'.format(uuid=self.tileset.uuid)).content)

        self.assertTrue('{uuid}.1.5.5'.format(uuid=self.tileset.uuid) not in returned.keys())

        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.20.5.5'.format(uuid=self.tileset.uuid)).content)

        self.assertTrue('{uuid}.1.5.5'.format(uuid=self.tileset.uuid) not in returned.keys())

    def test_get_hitile_tileset_info(self):
        '''
        returned = json.loads(self.client.get('/tilesets/x/tileset_info/?d={uuid}'.format(uuid=self.hitile.uuid)).content)

        self.assertTrue("{uuid}".format(uuid = self.hitile.uuid) in returned.keys())
        '''
        pass


# Create your tests here.
