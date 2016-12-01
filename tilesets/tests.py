from django.test import TestCase

from tilesets.models import Tileset
from django.urls import reverse

import base64
import json
import numpy as np


class TilesetsViewSetTest(TestCase):
    def setUp(self):
        self.tileset = Tileset.objects.create(processed_file='data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool',
                    file_type='cooler')

    def test_get_many_tiles(self):
        '''
        Test to make sure that requesting multiple tiles returns a JSON object with an entry for
        each tile.
        '''

        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.1.0.0&d={uuid}.1.0.1'.format(uuid=self.tileset.uuid)).content)

        print returned.keys()
        self.assertTrue('{uuid}.1.0.0'.format(uuid=self.tileset.uuid) in returned.keys())
        self.assertTrue('{uuid}.1.0.1'.format(uuid=self.tileset.uuid) in returned.keys())

    def test_get_same_tiles(self):
        '''
        Test to make sure that we return tileset info for 1D tracks
        '''
        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.1.0.0&d={uuid}.1.0.0'.format(uuid=self.tileset.uuid)).content)

        self.assertEquals(len(returned.keys()), 1)

        pass



# Create your tests here.
