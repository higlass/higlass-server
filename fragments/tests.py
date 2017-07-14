import django.core.files.uploadedfile as dcfu
import django.test as dt
import django.contrib.auth.models as dcam
import tilesets.models as tm
import json


class FragmentsTest(dt.TestCase):
    def setUp(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        upload_file = open(
            (
                'data/dixon2012-h1hesc-hindiii-allreps-filtered.1000kb'
                '.multires.cool'
            ),
            'rb'
        )
        self.cooler = tm.Tileset.objects.create(
            datafile=dcfu.SimpleUploadedFile(
                upload_file.name, upload_file.read()
            ),
            filetype='cooler',
            uuid='c1',
            owner=self.user1
        )

    def test_get_fragments(self):
        data = {
            "loci": [
                [
                    "chr1",
                    1000000000,
                    2000000000,
                    "1",
                    1000000000,
                    2000000000,
                    "c1",
                    0
                ]
            ]
        }

        ret = self.client.post(
            '/api/v1/fragments_by_loci/?precision=2&dims=22',
            json.dumps(data),
            content_type="application/json"
        )

        print(ret.status_code)
