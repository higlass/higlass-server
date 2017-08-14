import django.core.files.uploadedfile as dcfu
import django.test as dt
import django.contrib.auth.models as dcam
import tilesets.models as tm
import json
import numpy as np

from urllib.parse import urlencode


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

    def test_string_request_body(self):
        data = (
            '{loci: [["chr1", 1000000000, 2000000000, "1",'
            ' 1000000000, 2000000000, "c1", 0]]}'
        )

        response = self.client.post(
            '/api/v1/fragments_by_loci/?precision=2&dims=22',
            json.dumps(data),
            content_type="application/json"
        )

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertEqual(response.status_code, 400)
        self.assertTrue('error' in ret)
        self.assertTrue('error_message' in ret)

    def test_both_body_data_types(self):
        loci = [
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

        obj = {
            "loci": loci
        }

        response = self.client.post(
            '/api/v1/fragments_by_loci/?precision=2&dims=22',
            json.dumps(obj),
            content_type="application/json"
        )
        ret = json.loads(str(response.content, encoding='utf8'))

        mat1 = np.array(ret['fragments'][0], float)

        response = self.client.post(
            '/api/v1/fragments_by_loci/?precision=2&dims=22',
            json.dumps(loci),
            content_type="application/json"
        )
        ret = json.loads(str(response.content, encoding='utf8'))

        mat2 = np.array(ret['fragments'][0], float)

        self.assertTrue(np.array_equal(mat1, mat2))

    def test_domains_by_loci(self):
        data = {
            "loci": [
                [
                    "chr1",
                    0,
                    2000000000,
                    "1",
                    0,
                    2000000000,
                    "c1",
                    0
                ]
            ]
        }

        response = self.client.post(
            '/api/v1/fragments_by_loci/?precision=2&dims=44',
            json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertTrue('fragments' in ret)

        self.assertEqual(len(ret['fragments']), 1)

        self.assertEqual(len(ret['fragments'][0]), 44)

        self.assertEqual(len(ret['fragments'][0][0]), 44)

    def test_domains_normalizing(self):
        data = {
            "loci": [
                [
                    "chr2",
                    0,
                    500000000,
                    "2",
                    0,
                    500000000,
                    "c1",
                    0
                ]
            ]
        }

        params = {
            'dims': 60,
            'precision': 3,
            'padding': 2,
            'ignore-diags': 2,
            'percentile': 50
        }

        response = self.client.post(
            '/api/v1/fragments_by_loci/?{}'.format(urlencode(params)),
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertTrue('fragments' in ret)

        mat = np.array(ret['fragments'][0], float)

        # Make sure matrix is not empty
        self.assertTrue(np.sum(mat) > 0)

        # Check that the diagonal is zero
        diag = np.diag_indices(params['dims'])
        self.assertEqual(np.sum(mat[diag]), 0)
        self.assertEqual(
            np.sum(
                mat[((diag[0] - 1)[1:], diag[1][1:])]
            ),
            0
        )
        self.assertEqual(
            np.sum(
                mat[((diag[0] + 1)[:-1], diag[1][:-1])]
            ),
            0
        )

        # Check precision of matrix
        self.assertTrue(np.array_equal(mat, np.rint(mat * 1000) / 1000))
        self.assertTrue(not np.array_equal(mat, np.rint(mat * 100) / 100))

        # Check max
        self.assertEqual(np.max(mat), 1.0)

        # Get two more un-normalized matrices
        params1 = {
            'dims': 60,
            'precision': 3,
            'padding': 2,
            'ignore-diags': 2,
            'percentile': 50.0,
            'no-normalize': True
        }

        response = self.client.post(
            '/api/v1/fragments_by_loci/?{}'.format(urlencode(params1)),
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertTrue('fragments' in ret)

        mat1 = np.array(ret['fragments'][0], float)

        params2 = {
            'dims': 60,
            'precision': 3,
            'padding': 2,
            'ignore-diags': 2,
            'percentile': 100.0,
            'no-normalize': True
        }

        response = self.client.post(
            '/api/v1/fragments_by_loci/?{}'.format(urlencode(params2)),
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        ret = json.loads(str(response.content, encoding='utf8'))

        self.assertTrue('fragments' in ret)

        mat2 = np.array(ret['fragments'][0], float)

        # Make sure matrix is not empty
        self.assertTrue(np.sum(mat2) > 0)
        max1 = np.max(mat1)
        max2 = np.max(mat2)

        self.assertTrue(max2 > max1)

        percentile = np.percentile(mat2, params['percentile'])

        self.assertEqual(
            np.rint(max1 * 10000000) / 10000000,
            np.rint(percentile * 10000000) / 10000000
        )
