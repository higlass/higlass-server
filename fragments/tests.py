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

        response = self.client.post(
            '/api/v1/fragments_by_loci/?precision=2&dims=22',
            json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertTrue('fragments' in ret)

        self.assertEqual(len(ret['fragments']), 1)

        self.assertEqual(len(ret['fragments'][0]), 22)

        self.assertEqual(len(ret['fragments'][0][0]), 22)

    def test_domains_by_loci(self):
        data = {
            "loci": [
                [
                    "chr1",
                    0,
                    5000000,
                    "1",
                    0,
                    5000000,
                    "c1",
                    0
                ]
            ]
        }

        response = self.client.post(
            '/api/v1/domains_by_loci/?precision=2&dims=44',
            json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertTrue('fragments' in ret)

        self.assertEqual(len(ret['fragments']), 1)

        self.assertEqual(len(ret['fragments'][0]), 44)

        self.assertEqual(len(ret['fragments'][0][0]), 44)
