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
    calc_measure_dtd,
    calc_measure_size,
    calc_measure_noise,
    calc_measure_sharpness,
    get_frag_by_loc_from_cool,
    get_frag_by_loc_from_imtiles,
    get_intra_chr_loops_from_looplist,
    rel_loci_2_obj
)
from higlass_server.utils import getRdb

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
        padding = int(request.GET.get('padding', 0))
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
                            'error': 'Tileset not in database',
                        }, status=500)
            else:
                return JsonResponse({
                    'error': 'Tileset not specified',
                }, status=500)

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

    filetype = (
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
                        padding=padding,
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

                if filetype == 'imtiles':
                    sub_ims = get_frag_by_loc_from_imtiles(
                        imtiles_file=dataset,
                        loci=loci_lists[dataset][zoomout_level],
                        zoom_level=zoomout_level,
                        padding=padding,
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
def fragments_by_chr(request):
    chrom = request.GET.get('chrom', False)
    cooler_file = request.GET.get('cooler', False)
    loop_list = request.GET.get('loop-list', False)

    if cooler_file:
        if cooler_file.endswith('.cool'):
            cooler_file = path.join('data', cooler_file)
        else:
            try:
                cooler_file = get_datapath(
                    Tileset.objects.get(uuid=cooler_file).datafile.url
                )
            except AttributeError:
                return JsonResponse({
                    'error': 'Cooler file not in database',
                }, status=500)
    else:
        return JsonResponse({
            'error': 'Cooler file not specified',
        }, status=500)

    try:
        measures = request.GET.getlist('measures', [])
    except ValueError:
        measures = []

    try:
        zoomout_level = int(request.GET.get('zoomout-level', -1))
    except ValueError:
        zoomout_level = -1

    try:
        limit = int(request.GET.get('limit', -1))
    except ValueError:
        limit = -1

    try:
        precision = int(request.GET.get('precision', False))
    except ValueError:
        precision = False

    try:
        no_cache = bool(request.GET.get('no-cache', False))
    except ValueError:
        no_cache = False

    try:
        for_config = bool(request.GET.get('for-config', False))
    except ValueError:
        for_config = False

    # Get a unique string for the URL query string
    uuid = hashlib.md5(
        '-'.join([
            cooler_file,
            chrom,
            loop_list,
            str(limit),
            str(precision),
            str(zoomout_level)
        ])
    ).hexdigest()

    # Check if something is cached
    if not no_cache:
        try:
            results = rdb.get('frag_by_chrom_%s' % uuid)

            if results:
                return JsonResponse(pickle.loads(results))
        except:
            pass

    # Get relative loci
    try:
        (loci_rel, chroms) = get_intra_chr_loops_from_looplist(
            path.join('data', loop_list), chrom
        )
    except Exception as e:
        return JsonResponse({
            'error': 'Could not retrieve loci.',
            'error_message': str(e)
        }, status=500)

    # Convert to chromosome-relative loci list
    loci_rel_chroms = np.column_stack(
        (chroms[:, 0], loci_rel[:, 0:2], chroms[:, 1], loci_rel[:, 2:4])
    )

    if limit > 0:
        loci_rel_chroms = loci_rel_chroms[:limit]

    # Get fragments
    try:
        matrices = get_frag_by_loc(
            cooler_file,
            loci_rel_chroms,
            zoomout_level=zoomout_level
        )
    except Exception as e:
        return JsonResponse({
            'error': 'Could not retrieve fragments.',
            'error_message': str(e)
        }, status=500)

    if precision > 0:
        matrices = np.around(matrices, decimals=precision)

    fragments = []

    loci_struct = rel_loci_2_obj(loci_rel_chroms)

    # Check supported measures
    measures_applied = []
    for measure in measures:
        if measure in SUPPORTED_MEASURES:
            measures_applied.append(measure)

    i = 0
    for matrix in matrices:
        measures_values = []

        for measure in measures:
            if measure == 'distance-to-diagonal':
                measures_values.append(
                    calc_measure_dtd(matrix, loci_struct[i])
                )

            if measure == 'size':
                measures_values.append(
                    calc_measure_size(matrix, loci_struct[i])
                )

            if measure == 'noise':
                measures_values.append(calc_measure_noise(matrix))

            if measure == 'sharpness':
                measures_values.append(calc_measure_sharpness(matrix))

        frag_obj = {
            # 'matrix': matrix.tolist()
        }

        frag_obj.update(loci_struct[i])
        frag_obj.update({
            "measures": measures_values
        })
        fragments.append(frag_obj)
        i += 1

    # Create results
    results = {
        'count': matrices.shape[0],
        'dims': matrices.shape[1],
        'fragments': fragments,
        'measures': measures_applied,
        'relativeLoci': True,
        'zoomoutLevel': zoomout_level
    }

    if for_config:
        results['fragmentsHeader'] = [
            'chrom1',
            'start1',
            'end1',
            'strand1',
            'chrom2',
            'start2',
            'end2',
            'strand2'
        ] + measures_applied

        fragments_arr = []
        for fragment in fragments:
            tmp = [
                fragment['chrom1'],
                fragment['start1'],
                fragment['end1'],
                fragment['strand1'],
                fragment['chrom2'],
                fragment['start2'],
                fragment['end2'],
                fragment['strand2'],
            ] + fragment['measures']

            fragments_arr.append(tmp)

        results['fragments'] = fragments_arr

    # Cache results for 30 mins
    rdb.set('frag_by_chrom_%s' % uuid, pickle.dumps(results), 60 * 30)

    return JsonResponse(results)


@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def loci(request):
    chrom = request.GET.get('chrom', False)
    loop_list = request.GET.get('loop-list', False)

    # Get relative loci
    (loci_rel, chroms) = get_intra_chr_loops_from_looplist(
        path.join('data', loop_list), chrom
    )

    loci_rel_chroms = np.column_stack(
        (chroms[:, 0], loci_rel[:, 0:2], chroms[:, 1], loci_rel[:, 2:4])
    )

    # Create results
    results = {
        'loci': rel_loci_2_obj(loci_rel_chroms)
    }

    return JsonResponse(results)
