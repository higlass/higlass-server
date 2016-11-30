from django.test import TestCase

from tilesets.models import Tileset
from django.urls import reverse

import json


class TilesetsViewSetTest(TestCase):

    def test_get_many_tiles(self):
        '''
        Test to make sure that requesting multiple tiles returns a JSON object with an entry for
        each tile.
        '''
        t = Tileset.objects.create(processed_file='data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb.multires.cool',
                    file_type='cooler')

        returned = json.loads(self.client.get('/tilesets/x/render/?d={uuid}.1.0.0&d={uuid}.1.0.1'.format(uuid=t.uuid)).content)

        print returned.keys()
        self.assertTrue('{uuid}.1.0.0'.format(uuid=t.uuid) in returned.keys())
        self.assertTrue('{uuid}.1.0.1'.format(uuid=t.uuid) in returned.keys())


# Create your tests here.
