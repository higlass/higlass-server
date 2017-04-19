# coding=utf-8

from __future__ import print_function

from rest_framework.authentication import BasicAuthentication
from fragments.drf_disable_csrf import CsrfExemptSessionAuthentication

import logging
import csv

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, authentication_classes

from chroms.models import Sizes

import sys
reload(sys)
sys.setdefaultencoding('utf-8')


logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def sizes(request):
    '''Return chromosome sizes.

    Retrieves the chromSiyes.tsv and either retrieves it as is or converts it
    to a JSON format.

    Args:
        request: HTTP GET request object. The request can feature the following
            queries:

            id: id of the stored chromSizes [e.g.: hg19 or mm9]
            type: return data format [tsv or json]
            cum: return cumulative size or offset [0 or 1]

    Returns:
        A HTTP text or JSON response depending on the GET request.

        A text response looks like this:
        ```
        chr1    1
        chr2    2
        ...
        ```

        A JSON response looks like this:
        ```
        {
            chr1: {
                size: 1,
                offset: 0
            }
            chr2: {
                size: 2,
                offset: 1
            },
            ...
        }
        ```
    '''
    uuid = request.GET.get('id', False)
    res_type = request.GET.get('type', 'tsv')
    incl_cum = request.GET.get('cum', False)

    response = HttpResponse
    is_json = False

    if res_type == 'json':
        is_json = True
        response = JsonResponse

    if res_type != 'json' and incl_cum:
        return response(
            'Sorry buddy. Cumulative sizes not yet supported for non-JSON '
            'file types. 😞', status=501
        )

    # Try to find the db entry
    try:
        chrom_sizes = Sizes.objects.get(uuid=uuid)
    except Exception as e:
        logger.error(e)
        err_msg = 'Oh lord! ChromSizes for %s not found. ☹️' % uuid
        err_status = 404

        if is_json:
            return response({'error': err_msg}, status=err_status)

        return response(err_msg, status=err_status)

    # Try to load the CSV file
    try:
        f = chrom_sizes.datafile
        f.open('rb')

        if res_type == 'json':
            reader = csv.reader(f, delimiter='\t')

            data = []
            for row in reader:
                data.append(row)
        else:
            data = f.readlines()

        f.close()
    except Exception as e:
        logger.error(e)
        err_msg = 'WHAT?! Could not load file %s. 😤 (%s)' % (
            chrom_sizes.datafile, e
        )
        err_status = 500

        if is_json:
            return response({'error': err_msg}, status=err_status)

        return response(err_msg, status=err_status)

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
        err_msg = 'THIS IS AN OUTRAGE!!!1! Something failed. 😡'
        err_status = 500

        if is_json:
            return response({'error': err_msg}, status=err_status)

        return response(err_msg, status=err_status)

    return response(data)
