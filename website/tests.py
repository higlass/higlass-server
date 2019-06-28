import os
import os.path as op
from unittest import TestCase, mock

import django.test as dt
import website.views as wv

import higlass_server.settings as hss

class SiteTests(dt.TestCase):
    def test_link_url(self):
        ret = self.client.get('/link')

        assert ret.content.decode('utf8').find('window.location') >= 0

    def test_thumbnail(self):
        # mock_hss.configure_mock(THUMBNAILS_ROOT=op.join(hss.MEDIA_ROOT, 'thumbnails'))
        # mock_hss.configure_mock(THUMBNAIL_RENDER_URL_BASE='http://higlass.io/app')

        uuid = 'L4nKi6eGSzWOpi-rU2DAMA'
        output_file = op.join(hss.THUMBNAILS_ROOT, uuid + ".png")

        if op.exists(output_file):
            os.remove(output_file)

        ret = self.client.get(
            '/thumbnail/?d=L4nKi6eGSzWOpi-rU2DAMA'
        )

        self.assertEqual(ret.status_code, 200)
