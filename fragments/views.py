from __future__ import print_function

import hashlib
import json
import logging
import numpy as np
import pybase64
from PIL import Image
try:
    import cPickle as pickle
except:
    import pickle

import higlass_server.settings as hss

from rest_framework.authentication import BasicAuthentication
from .drf_disable_csrf import CsrfExemptSessionAuthentication
from io import BytesIO
from os import path
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, authentication_classes
from tilesets.models import Tileset
from fragments.utils import (
    calc_measure_dtd,
    calc_measure_size,
    calc_measure_noise,
    calc_measure_sharpness,
    aggregate_frags,
    get_frag_by_loc_from_cool,
    get_frag_by_loc_from_imtiles,
    get_frag_by_loc_from_osm,
    get_intra_chr_loops_from_looplist,
    get_params,
    get_rep_frags,
    rel_loci_2_obj,
    np_to_png,
    write_png,
    grey_to_rgb,
    blob_to_zip
)
from higlass_server.utils import getRdb
from fragments.exceptions import SnippetTooLarge

import h5py

from math import floor, log

rdb = getRdb()

logger = logging.getLogger(__name__)

SUPPORTED_MEASURES = ['distance-to-diagonal', 'noise', 'size', 'sharpness']

SUPPORTED_FILETYPES = ['matrix', 'im-tiles', 'osm-tiles']

GET_FRAG_PARAMS = {
    'dims': {
        'short': 'di',
        'dtype': 'int',
        'default': 22,
        'help': 'Global number of dimensions. (Only used for cooler tilesets.)'
    },
    'padding': {
        'short': 'pd',
        'dtype': 'float',
        'default': 0,
        'help': 'Add given percent of the fragment size as padding.'
    },
    'no-balance': {
        'short': 'nb',
        'dtype': 'bool',
        'default': False,
        'help': (
            'Do not balance fragmens if true. (Only used for cooler tilesets.)'
        )
    },
    'percentile': {
        'short': 'pe',
        'dtype': 'float',
        'default': 100.0,
        'help': (
            'Cap values at given percentile. (Only used for cooler tilesets.)'
        )
    },
    'precision': {
        'short': 'pr',
        'dtype': 'int',
        'default': 0,
        'help': (
            'Number of decimals of the numerical values. '
            '(Only used for cooler tilesets.)'
        )
    },
    'no-cache': {
        'short': 'nc',
        'dtype': 'bool',
        'default': 0,
        'help': 'Do not cache fragments if true. Useful for debugging.'
    },
    'ignore-diags': {
        'short': 'nd',
        'dtype': 'int',
        'default': 0,
        'help': (
            'Ignore N diagonals, i.e., set them to zero. '
            '(Only used for cooler tilesets.)'
        )
    },
    'no-normalize': {
        'short': 'nn',
        'dtype': 'bool',
        'default': False,
        'help': (
            'Do not normalize fragments if true. '
            '(Only used for cooler tilesets.)'
        )
    },
    'aggregate': {
        'short': 'ag',
        'dtype': 'bool',
        'default': False,
        'help': 'Aggregate fragments if true.'
    },
    'aggregation-method': {
        'short': 'am',
        'dtype': 'str',
        'default': 'mean',
        'help': 'Aggregation method: mean, median, std, var.'
    },
    'max-previews': {
        'short': 'mp',
        'dtype': 'int',
        'default': 0,
        'help': (
            'Max. number of 1D previews to return. When the number of '
            'fragments s higher than the previews we cluster the frags by '
            'k-means.'
        )
    },
    'encoding': {
        'short': 'en',
        'dtype': 'str',
        'default': 'matrix',
        'help': (
            'Data encoding: matrix, b64, or image. (Image encoding only '
            'supported when one fragment is to be returned)'
        )
    },
    'representatives': {
        'short': 'rp',
        'dtype': 'int',
        'default': 0,
        'help': (
            'Number of representative fragments when requesting multiple '
            'fragments.'
        )
    },
}


@api_view(['GET', 'POST'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def fragments_by_loci(request):
    if request.method == 'GET':
        return get_fragments_by_loci_info(request)

    return get_fragments_by_loci(request)


def get_fragments_by_loci_info(request):
    return JsonResponse(GET_FRAG_PARAMS)


def get_fragments_by_loci(request):
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
        forced_rep_idx = request.data.get('representativeIndices', None)
    except Exception as e:
        forced_rep_idx = None
        pass

    '''
    Loci list must be of type:
    [cooler]          [imtiles]
    0: chrom1         start1
    1: start1         end1
    2: end1           start2
    3: chrom2         end2
    4: start2         dataset
    5: end2           zoomLevel
    6: dataset        dim*
    7: zoomOutLevel
    8: dim*

    *) Optional
    '''

    params = get_params(request, GET_FRAG_PARAMS)

    dims = params['dims']
    padding = params['padding']
    no_balance = params['no-balance']
    percentile = params['percentile']
    precision = params['precision']
    no_cache = params['no-cache']
    ignore_diags = params['ignore-diags']
    no_normalize = params['no-normalize']
    aggregate = params['aggregate']
    aggregation_method = params['aggregation-method']
    max_previews = params['max-previews']
    encoding = params['encoding']
    representatives = params['representatives']

    # Check if requesting a snippet from a `.cool` cooler file
    is_cool = len(loci) and len(loci[0]) > 7
    tileset_idx = 6 if is_cool else 4
    zoom_level_idx = tileset_idx + 1

    filetype = None
    new_filetype = None
    previews = []
    previews_2d = []
    ts_cache = {}
    mat_idx = None

    total_valid_loci = 0
    loci_lists = {}
    loci_ids = []
    try:
        for locus in loci:
            tileset_file = ''

            if locus[tileset_idx]:
                if locus[tileset_idx] in ts_cache:
                    tileset = ts_cache[locus[tileset_idx]]['obj']
                    tileset_file = ts_cache[locus[tileset_idx]]['path']
                elif locus[tileset_idx].endswith('.cool'):
                    tileset_file = path.join('data', locus[tileset_idx])
                else:
                    try:
                        tileset = Tileset.objects.get(
                            uuid=locus[tileset_idx]
                        )
                        tileset_file = tileset.datafile.path
                        ts_cache[locus[tileset_idx]] = {
                            "obj": tileset,
                            "path": tileset_file
                        }

                    except AttributeError:
                        return JsonResponse({
                            'error': 'Tileset ({}) does not exist'.format(
                                locus[tileset_idx]
                            ),
                        }, status=400)
                    except Tileset.DoesNotExist:
                        if locus[tileset_idx].startswith('osm'):
                            new_filetype = locus[tileset_idx]
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

            # Get the dimensions of the snippets (i.e., width and height in px)
            inset_dim = (
                locus[zoom_level_idx + 1]
                if (
                    len(locus) >= zoom_level_idx + 2 and
                    locus[zoom_level_idx + 1]
                )
                else None
            )
            out_dim = dims if inset_dim is None else inset_dim

            # Make sure out dim (in pixel) is not too large
            if (
                (is_cool and out_dim > hss.SNIPPET_MAT_MAX_OUT_DIM) or
                (not is_cool and out_dim > hss.SNIPPET_IMG_MAX_OUT_DIM)
            ):
                return JsonResponse({
                    'error': 'Snippet too large',
                    'error_message': str(SnippetTooLarge())
                }, status=400)

            if tileset_file not in loci_lists:
                loci_lists[tileset_file] = {}

            if is_cool:
                # Get max abs dim in base pairs
                max_abs_dim = max(locus[2] - locus[1], locus[5] - locus[4])

                with h5py.File(tileset_file, 'r') as f:
                    # get base resolution (bin size) of cooler file
                    if 'resolutions' in f:
                        # v2
                        resolutions = sorted(
                            [int(key) for key in f['resolutions'].keys()]
                        )
                        closest_res = 0
                        for i, res in enumerate(resolutions):
                            if (max_abs_dim / out_dim) - res < 0:
                                closest_res = resolutions[max(0, i - 1)]
                                break
                        zoomout_level = (
                            locus[zoom_level_idx]
                            if locus[zoom_level_idx] >= 0
                            else closest_res
                        )
                    else:
                        # v1
                        max_zoom = f.attrs['max-zoom']
                        bin_size = int(f[str(max_zoom)].attrs['bin-size'])

                        # Find closest zoom level if `zoomout_level < 0`
                        # Assuming resolutions of powers of 2
                        zoomout_level = (
                            locus[zoom_level_idx]
                            if locus[zoom_level_idx] >= 0
                            else floor(log((max_abs_dim / bin_size) / out_dim, 2))
                        )

            else:
                # Get max abs dim in base pairs
                max_abs_dim = max(locus[1] - locus[0], locus[3] - locus[2])

                bin_size = 1

                # Find closest zoom level if `zoomout_level < 0`
                # Assuming resolutions of powers of 2
                zoomout_level = (
                    locus[zoom_level_idx]
                    if locus[zoom_level_idx] >= 0
                    else floor(log((max_abs_dim / bin_size) / out_dim, 2))
                )

            if zoomout_level not in loci_lists[tileset_file]:
                loci_lists[tileset_file][zoomout_level] = []

            locus_id = '.'.join(map(str, locus))

            loci_lists[tileset_file][zoomout_level].append(
                locus[0:tileset_idx] + [total_valid_loci, inset_dim, locus_id]
            )
            loci_ids.append(locus_id)

            if new_filetype is None:
                new_filetype = (
                    tileset.filetype
                    if tileset
                    else tileset_file[tileset_file.rfind('.') + 1:]
                )

            if filetype is None:
                filetype = new_filetype

            if filetype != new_filetype:
                return JsonResponse({
                    'error': (
                        'Multiple file types per query are not supported yet.'
                    )
                }, status=400)

            total_valid_loci += 1

    except Exception as e:
        return JsonResponse({
            'error': 'Could not convert loci.',
            'error_message': str(e)
        }, status=500)

    mat_idx = list(range(len(loci_ids)))

    # Get a unique string for caching
    dump = (
        json.dumps(loci, sort_keys=True) +
        str(forced_rep_idx) +
        str(dims) +
        str(padding) +
        str(no_balance) +
        str(percentile) +
        str(precision) +
        str(ignore_diags) +
        str(no_normalize) +
        str(aggregate) +
        str(aggregation_method) +
        str(max_previews) +
        str(encoding) +
        str(representatives)
    )
    uuid = hashlib.md5(dump.encode('utf-8')).hexdigest()

    # Check if something is cached
    if not no_cache:
        try:
            results = rdb.get('frag_by_loci_%s' % uuid)
            if results:
                return JsonResponse(pickle.loads(results))
        except:
            pass

    matrices = [None] * total_valid_loci
    data_types = [None] * total_valid_loci
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
                        no_normalize=no_normalize,
                        aggregate=aggregate,
                    )

                    for i, matrix in enumerate(raw_matrices):
                        idx = loci_lists[dataset][zoomout_level][i][6]
                        matrices[idx] = matrix
                        data_types[idx] = 'matrix'

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
                        no_cache=no_cache,
                    )

                    for i, im in enumerate(sub_ims):
                        idx = loci_lists[dataset][zoomout_level][i][4]

                        matrices[idx] = im

                        data_types[idx] = 'matrix'

    except Exception as ex:
        raise
        return JsonResponse({
            'error': 'Could not retrieve fragments.',
            'error_message': str(ex)
        }, status=500)

    if aggregate and len(matrices) > 1:
        try:
            cover, previews_1d, previews_2d = aggregate_frags(
                matrices,
                loci_ids,
                aggregation_method,
                max_previews,
            )
            matrices = [cover]
            mat_idx = []
            if previews_1d is not None:
                previews = np.split(
                    previews_1d, range(1, previews_1d.shape[0])
                )
            data_types = [data_types[0]]
        except Exception as ex:
            raise
            return JsonResponse({
                'error': 'Could not aggregate fragments.',
                'error_message': str(ex)
            }, status=500)

    if representatives and len(matrices) > 1:
        if forced_rep_idx and len(forced_rep_idx) <= len(matrices):
            matrices = [matrices[i] for i in forced_rep_idx]
            mat_idx = forced_rep_idx
            data_types = [data_types[0]] * len(forced_rep_idx)
        else:
            try:
                rep_frags, rep_idx = get_rep_frags(
                    matrices, loci, loci_ids, representatives, no_cache
                )
                matrices = rep_frags
                mat_idx = rep_idx
                data_types = [data_types[0]] * len(rep_frags)
            except Exception as ex:
                raise
                return JsonResponse({
                    'error': 'Could get representative fragments.',
                    'error_message': str(ex)
                }, status=500)

    if encoding != 'b64' and encoding != 'image':
        # Adjust precision and convert to list
        for i, matrix in enumerate(matrices):
            if precision > 0:
                matrix = np.round(matrix, decimals=precision)
            matrices[i] = matrix.tolist()

        if max_previews > 0:
            for i, preview in enumerate(previews):
                previews[i] = preview.tolist()
            for i, preview_2d in enumerate(previews_2d):
                previews_2d[i] = preview_2d.tolist()

    # Encode matrix if required
    if encoding == 'b64':
        for i, matrix in enumerate(matrices):
            id = loci_ids[mat_idx[i]]
            data_types[i] = 'dataUrl'
            if not no_cache and id:
                mat_b64 = None
                try:
                    mat_b64 = rdb.get('im_b64_%s' % id)
                    if mat_b64 is not None:
                        matrices[i] = mat_b64.decode('ascii')
                        continue
                except:
                    pass

            mat_b64 = pybase64.b64encode(np_to_png(matrix)).decode('ascii')

            if not no_cache:
                try:
                    rdb.set('im_b64_%s' % id, mat_b64, 60 * 30)
                except Exception as ex:
                    # error caching a tile
                    # log the error and carry forward, this isn't critical
                    logger.warn(ex)

            matrices[i] = mat_b64

        if max_previews > 0:
            for i, preview in enumerate(previews):
                previews[i] = pybase64.b64encode(
                    np_to_png(preview)
                ).decode('ascii')
            for i, preview_2d in enumerate(previews_2d):
                previews_2d[i] = pybase64.b64encode(
                    np_to_png(preview_2d)
                ).decode('ascii')

    # Create results
    results = {
        'fragments': matrices,
        'indices': [int(i) for i in mat_idx],
        'dataTypes': data_types,
    }

    # Return Y aggregates as 1D previews on demand
    if max_previews > 0:
        results['previews'] = previews
        results['previews2d'] = previews_2d

    # Cache results for 30 minutes
    try:
        rdb.set('frag_by_loci_%s' % uuid, pickle.dumps(results), 60 * 30)
    except Exception as ex:
        # error caching a tile
        # log the error and carry forward, this isn't critical
        logger.warn(ex)

    if encoding == 'image':
        if len(matrices) == 1:
            return HttpResponse(
                np_to_png(grey_to_rgb(matrices[0], to_rgba=True)),
                content_type='image/png'
            )
        else:
            ims = []
            for i, matrix in enumerate(matrices):
                ims.append({
                    'name': '{}.png'.format(i),
                    'bytes': np_to_png(grey_to_rgb(matrix, to_rgba=True))
                })
            return blob_to_zip(ims, to_resp=True)

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
                cooler_file = Tileset.objects.get(uuid=cooler_file).datafile.path
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
    try:
        rdb.set('frag_by_chrom_%s' % uuid, pickle.dumps(results), 60 * 30)
    except Exception as ex:
        # error caching a tile
        # log the error and carry forward, this isn't critical
        logger.warn(ex)

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
