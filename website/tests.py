import json
import os
import os.path as op
from asynctest import CoroutineMock

from pathlib import Path
from unittest import TestCase, mock

import django.contrib.auth.models as dcam
import django.test as dt
import tilesets.models as tm
import website.views as wv

import higlass_server.settings as hss

class SiteTests(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )

        upload_json_text = json.dumps({'hi': 'there'})

        self.viewconf = tm.ViewConf.objects.create(
                viewconf=upload_json_text, uuid='md')

    def test_link_url(self):
        ret = self.client.get('/link/')
        assert "No uuid specified" in ret.content.decode('utf8')

        ret = self.client.get('/link/?d=x')
        assert ret.status_code == 404

        ret = self.client.get('/link/?d=md')
        assert ret.content.decode('utf8').find('window.location') >= 0

    @mock.patch('website.views.screenshot', new=CoroutineMock())
    def test_thumbnail(self):
        uuid = 'some_fake_uid'
        output_file = Path(hss.THUMBNAILS_ROOT) / (uuid + ".png")

        if not output_file.exists():
            output_file.touch()

        ret = self.client.get(
            f'/thumbnail/?d={uuid}'
        )

        self.assertEqual(ret.status_code, 200)

        ret = self.client.get(
            f'/t/?d=..file'
        )

        self.assertEqual(ret.status_code, 400)
