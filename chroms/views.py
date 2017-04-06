# coding=utf-8

from __future__ import print_function

from rest_framework.authentication import BasicAuthentication
from fragments.drf_disable_csrf import CsrfExemptSessionAuthentication

import logging
import csv
import os

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, authentication_classes

from chroms.models import Sizes
from django.conf import settings

import sys
reload(sys)
sys.setdefaultencoding('utf-8')


logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def sizes(request):
    coords = request.GET.get('coords', False)
    res_type = request.GET.get('type', 'tsv')
    incl_cum = request.GET.get('cum', False)

    response = HttpResponse

    if res_type == 'json':
        response = JsonResponse

    if res_type != 'json' and incl_cum:
        return response({
            'error': (
                'Sorry buddy. Cumulative sizes not yet supported for non-JSON '
                'file types. 😞'
            )
        })

    # Try to find the db entry
    try:
        chrom_sizes = Sizes.objects.get(uuid=coords)
    except Exception as e:
        logger.error(e)
        return response({
            'error': 'Oh lord! ChromSizes for %s not found. ☹️' % coords
        })

    # Try to load the CSV file
    try:
        fpath = os.path.join(settings.MEDIA_ROOT, chrom_sizes.datafile)

        if res_type == 'json':
            with open(fpath, 'rb') as f:
                reader = csv.reader(f, delimiter='\t')

                data = []
                for row in reader:
                    data.append(row)
        else:
            with open(fpath) as f:
                data = f.readlines()
    except Exception as e:
        logger.error(e)
        return response({
            'error': 'WHAT?! Could not load file %s. 😤' % chrom_sizes.datafile
        })

    # Convert the stuff if needed
    try:
        if res_type == 'json' and not incl_cum:
            json_out = {}

            for row in data:
                json_out[row[0]] = {
                    'size': int(row[1])
                }

            data = json_out

        if res_type == 'json' and incl_cum:
            json_out = {}
            cum = 0

            for row in data:
                size = int(row[1])

                json_out[row[0]] = {
                    'size': size,
                    'offset': cum
                }
                cum += size

            data = json_out
    except Exception as e:
        logger.error(e)
        return response({
            'error': (
                'THIS IS AN OUTRAGE!!!1! Something failed. 😡'
            ),
            'errorMsg': str(e)
        })

    return response(data)
