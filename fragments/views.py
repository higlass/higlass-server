from __future__ import print_function

import base64
import hashlib
import json
import logging
import numpy as np
try:
    import cPickle as pickle
except:
    import pickle

from rest_framework.authentication import BasicAuthentication
from .drf_disable_csrf import CsrfExemptSessionAuthentication
from os import path
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes
from tilesets.models import Tileset
from tilesets.utils import get_datapath
from fragments.utils import (
    get_features,
    get_frag_by_loc_from_cool,
    get_frag_by_loc_from_imtiles,
    get_frag_by_loc_from_osm,
    get_intra_chr_loops_from_looplist,
    rel_loci_2_obj
)
from higlass_server.utils import getRdb

from hdbscan import HDBSCAN

rdb = getRdb()

logger = logging.getLogger(__name__)

SUPPORTED_MEASURES = ['distance-to-diagonal', 'noise', 'size', 'sharpness']


@api_view(['POST'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def fragments_by_loci(request):
    '''
    Retrieve a list of locations and return the corresponding matrix fragments

    Args:

    request (django.http.HTTPRequest): The request object containing the
        list of loci.

    Return:

    '''

    if type(request.data) is str:
        return JsonResponse({
            'error': 'Request body needs to be an array or object.',
            'error_message': 'Request body needs to be an array or object.'
        }, status=400)

    try:
        loci = request.data.get('loci', [])
    except AttributeError:
        loci = request.data
    except Exception as e:
        return JsonResponse({
            'error': 'Could not read request body.',
            'error_message': str(e)
        }, status=400)

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    try:
        no_cache = bool(request.GET.get('no-cache', False))
    except ValueError:
        no_cache = False

    try:
        dims = int(request.GET.get('dims', 22))
    except ValueError:
        dims = 22

    try:
        padding = request.GET.get('padding', 0)
    except ValueError:
        padding = 0

    try:
        no_balance = bool(request.GET.get('no-balance', False))
    except ValueError:
        no_balance = False

    try:
        percentile = float(request.GET.get('percentile', 100.0))
    except ValueError:
        percentile = 100.0

    try:
        ignore_diags = int(request.GET.get('ignore-diags', 0))
    except ValueError:
        ignore_diags = 0

    try:
        no_normalize = bool(request.GET.get('no-normalize', False))
    except ValueError:
        no_normalize = False

    '''
    Loci list must be of type:
    [cooler]          [imtiles]
    0: chrom1         start1
    1: start1         end1
    2: end1           start2
    3: chrom2         end2
    4: start2         dataset
    5: end2           zoomLevel
    6: dataset
    7: zoomOutLevel
    '''

    tileset_idx = 6 if len(loci) and len(loci[0]) > 6 else 4
    zoom_level_idx = tileset_idx + 1

    filetype = None

    i = 0
    loci_lists = {}
    try:
        for locus in loci:
            tileset_file = ''

            if locus[tileset_idx]:
                if locus[tileset_idx].endswith('.cool'):
                    tileset_file = path.join('data', locus[tileset_idx])
                else:
                    try:
                        tileset = Tileset.objects.get(
                            uuid=locus[tileset_idx]
                        )
                        tileset_file = get_datapath(
                            tileset.datafile.url
                        )

                    except AttributeError:
                        return JsonResponse({
                            'error': 'Tileset ({}) does not exist'.format(
                                locus[tileset_idx]
                            ),
                        }, status=400)
                    except Tileset.DoesNotExist:
                        if locus[tileset_idx].startswith('osm'):
                            filetype = locus[tileset_idx]
                        else:
                            return JsonResponse({
                                'error': 'Tileset ({}) does not exist'.format(
                                    locus[tileset_idx]
                                ),
                            }, status=400)
            else:
                return JsonResponse({
                    'error': 'Tileset not specified',
                }, status=400)

            if tileset_file not in loci_lists:
                loci_lists[tileset_file] = {}

            if locus[zoom_level_idx] not in loci_lists[tileset_file]:
                loci_lists[tileset_file][locus[zoom_level_idx]] = []

            loci_lists[tileset_file][locus[zoom_level_idx]].append(
                locus[0:tileset_idx] + [i]
            )

            i += 1

    except Exception as e:
        return JsonResponse({
            'error': 'Could not convert loci.',
            'error_message': str(e)
        }, status=500)

    filetype = filetype if filetype else (
        tileset.filetype
        if tileset
        else tileset_file[tileset_file.rfind('.') + 1:]
    )

    # Get a unique string for caching
    dump = json.dumps(loci, sort_keys=True) + str(precision) + str(dims)
    uuid = hashlib.md5(dump.encode('utf-8')).hexdigest()

    # Check if something is cached
    if not no_cache:
        try:
            results = rdb.get('frag_by_loci_%s' % uuid)

            if results:
                return JsonResponse(pickle.loads(results))
        except:
            pass

    matrices = [None] * i
    data_types = [None] * i
    try:
        for dataset in loci_lists:
            for zoomout_level in loci_lists[dataset]:
                if filetype == 'cooler' or filetype == 'cool':
                    raw_matrices = get_frag_by_loc_from_cool(
                        dataset,
                        loci_lists[dataset][zoomout_level],
                        dims,
                        zoomout_level=zoomout_level,
                        balanced=not no_balance,
                        padding=int(padding),
                        percentile=percentile,
                        ignore_diags=ignore_diags,
                        no_normalize=no_normalize
                    )

                    if precision > 0:
                        raw_matrices = np.around(
                            raw_matrices, decimals=precision
                        )

                    i = 0
                    for raw_matrix in raw_matrices:
                        idx = loci_lists[dataset][zoomout_level][i][6]
                        matrices[idx] = raw_matrix.tolist()
                        data_types[idx] = 'matrix'
                        i += 1

                if filetype == 'imtiles' or filetype == 'osm-image':
                    extractor = (
                        get_frag_by_loc_from_imtiles
                        if filetype == 'imtiles'
                        else get_frag_by_loc_from_osm
                    )

                    sub_ims = extractor(
                        imtiles_file=dataset,
                        loci=loci_lists[dataset][zoomout_level],
                        zoom_level=zoomout_level,
                        padding=float(padding),
                    )

                    i = 0
                    for im in sub_ims:
                        idx = loci_lists[dataset][zoomout_level][i][4]

                        try:
                            # Store images as data URI
                            matrices[idx] = \
                                base64.b64encode(im[0]).decode('utf-8')
                        except TypeError:
                            matrices[idx] = None

                        data_types[idx] = 'dataUrl'

                        i += 1

    except Exception as ex:
        raise
        return JsonResponse({
            'error': 'Could not retrieve fragments.',
            'error_message': str(ex)
        }, status=500)

    # Create results
    results = {
        'fragments': matrices,
        'dataTypes': data_types
    }

    # Cache results for 30 minutes
    rdb.set('frag_by_loci_%s' % uuid, pickle.dumps(results), 60 * 30)

    return JsonResponse(results)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def cluster_fragments(request):
    '''Cluster small regions within a larger region
    '''

    try:
        zoom_level = int(request.GET.get('z', 0))
    except ValueError:
        return JsonResponse({
            'error': 'z (zoom level) needs to be a number',
        }, status=400)

    try:
        x_from = float(request.GET.get('x-from', 0))
    except ValueError:
        return JsonResponse({
            'error': 'x-from needs to be a number',
        }, status=400)

    try:
        x_to = float(request.GET.get('x-to', 0))
    except ValueError:
        return JsonResponse({
            'error': 'x-to needs to be a number',
        }, status=400)

    try:
        y_from = float(request.GET.get('y-from', 0))
    except ValueError:
        return JsonResponse({
            'error': 'y-from needs to be a number',
        }, status=400)

    try:
        y_to = float(request.GET.get('y-to', 0))
    except ValueError:
        return JsonResponse({
            'error': 'y-to needs to be a number',
        }, status=400)

    try:
        width = float(request.GET.get('w', 0))
    except ValueError:
        return JsonResponse({
            'error': 'w (width) needs to be a number',
        }, status=400)

    try:
        height = float(request.GET.get('h', 0))
    except ValueError:
        return JsonResponse({
            'error': 'h (height) needs to be a number',
        }, status=400)

    try:
        threshold = float(request.GET.get('t', 0))
    except ValueError:
        return JsonResponse({
            'error': 't (threshold) needs to be a number',
        }, status=400)

    try:
        num_cluster = float(request.GET.get('n', 0))
    except ValueError:
        return JsonResponse({
            'error': 'n (num clusters) needs to be a number',
        }, status=400)

    try:
        tile_set_uuids = str(request.GET.get('d', ''))
    except ValueError:
        return JsonResponse({
            'error': 'd (data set uuids) need to be specified',
        }, status=400)

    try:
        no_cache = bool(request.GET.get('no-cache', False))
    except ValueError:
        no_cache = False

    if tile_set_uuids:
        tile_set_uuids = tile_set_uuids.split(',')
    else:
        return JsonResponse({
            'error': 'No tile set uuids specified',
        }, status=400)

    try:
        # Map UUIDs to tile set objects
        tile_sets = list(map(
            lambda uuid: Tileset.objects.get(uuid=uuid),
            tile_set_uuids
        ))
    except Tileset.DoesNotExist:
        return JsonResponse({
            'error': 'one or more tile sets were not found',
        }, status=404)

    supported_filetypes = ['bed2ddb', '2dannodb', 'geodb']

    if not all(
        tile_set.filetype in supported_filetypes for tile_set in tile_sets
    ):
        return JsonResponse({
            'error': (
                'One or more tile sets are not supported. Only bed2ddb, '
                '2dannodb, and geodb are supported.'
            ),
        }, status=400)

    # Get a unique fingerprint for the URL query string
    fingerprint = hashlib.md5(
        '-'.join([
            str(x_from),
            str(x_to),
            str(y_from),
            str(y_to),
            str(width),
            str(height),
            str(threshold),
            str(num_cluster),
            '&'.join(tile_set_uuids),
        ]).encode('utf-8')
    ).hexdigest()

    # Check if something is cached
    if not no_cache:
        try:
            results = rdb.get('clust_frag_%s' % fingerprint)

            if results:
                return JsonResponse(pickle.loads(results))
        except:
            pass

    # Assemble features
    all_features = []
    for tile_set in tile_sets:
        features = get_features(
            tile_set, zoom_level, x_from, x_to, y_from, y_to
        )
        all_features += map(
            lambda x: np.mean([x[0:2], x[2:4]], axis=1), features
        )

    num_clust = 0

    if len(all_features) > 0:
        db = HDBSCAN(min_cluster_size=5).fit(all_features)

        # Get labels
        labels = db.labels_

        # "-1" is the cluster of noise
        num_clust = int(labels.max() + 1)

    # Cache results for 30 mins
    rdb.set('clust_frag_%s' % fingerprint, pickle.dumps(results), 60 * 30)

    results = {
        'num_clust': num_clust
    }

    return JsonResponse(results)
