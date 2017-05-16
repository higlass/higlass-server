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

import chroms.models as tm

logger = logging.getLogger(__name__)

class ChromosomeSizes(dt.TestCase):
    def test_list_chromsizes(self):
        self.user1 = dcam.User.objects.create_user(
            username='user1', password='pass'
        )
        upload_file = open('data/chromSizes.tsv', 'r')
        tm.Sizes.objects.create(
            datafile=dcfu.SimpleUploadedFile(upload_file.name, upload_file.read()),
            coords='hg19',
            uuid='hg19'
        )

        ret = json.loads(self.client.get('/api/v1/available-chrom-sizes/').content)

        assert(ret["count"] == 1)
        assert(len(ret["results"]) == 1)

        ret = self.client.get('/api/v1/chrom-sizes/?id=hg19').content

        assert(len(ret) > 300)
