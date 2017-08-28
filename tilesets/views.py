# -*- coding: utf-8 -*-
from __future__ import print_function

import base64
import csv
import clodius.hdf_tiles as hdft
import clodius.db_tiles as cdt
import collections as col
import django.db.models as dbm
import django.db.models.functions as dbmf
import cooler.contrib.higlass as cch
import guardian.utils as gu
import higlass_server.settings as hss
import h5py
import json
import logging
import math
import numpy as np
import os.path as op
import rest_framework.exceptions as rfe
import rest_framework.pagination as rfpa
import rest_framework.parsers as rfp
import rest_framework.status as rfs
import tilesets.models as tm
import tilesets.permissions as tsp
import tilesets.serializers as tss
import tilesets.suggestions as tsu
import slugid
import urllib

try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from rest_framework import generics
from rest_framework import viewsets
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.authentication import BasicAuthentication
from fragments.drf_disable_csrf import CsrfExemptSessionAuthentication
from .tiles import make_tiles

from higlass_server.utils import getRdb

logger = logging.getLogger(__name__)

global mats
mats = {}

rdb = getRdb()


def make_mats(dset):
    f = h5py.File(dset, 'r')
    info = cch.get_info(dset)

    info["min_pos"] = [int(m) for m in info["min_pos"]]
    info["max_pos"] = [int(m) for m in info["max_pos"]]
    info["max_zoom"] = int(info["max_zoom"])
    info["max_width"] = int(info["max_width"])

    if "transforms" in info:
        info["transforms"] = list(info["transforms"])

    mats[dset] = [f, info]


def make_cooler_tile(cooler_filepath, tile_position, transform_type='default'):
    '''Create a tile from a cooler file.

    Args:
        cooler_filepath (str): The location of the cooler file that we'll
            that we'll extract the tile data from.
        tile_position (list): The position of the tile ([z,x,y])
        transform_type (str): The method used to transform the data (

    Returns:
        dict: The tile data consisting of a 'dense' member containing
            the data array as well as 'min_value' and 'max_value' which
            contain the minimum and maximum values in the 'dense' array.
    '''

    tile_data = {}

    if cooler_filepath not in mats:
        make_mats(cooler_filepath)

    tileset_file_and_info = mats[cooler_filepath]

    if tile_position[0] > tileset_file_and_info[1]['max_zoom']:
        # we don't have enough zoom levels
        return None
    if tile_position[1] >= 2 ** tile_position[0]:
        # tile is out of bounds
        return None
    if tile_position[2] >= 2 ** tile_position[0]:
        # tile is out of bounds
        return None

    tile = make_tiles(
        tile_position[0],
        tile_position[1],
        tile_position[2],
        mats[cooler_filepath],
        transform_type
    )

    min_dense = float(np.min(tile))
    max_dense = float(np.max(tile))

    tile_data["min_value"] = min_dense
    tile_data["max_value"] = max_dense

    min_f16 = np.finfo('float16').min
    max_f16 = np.finfo('float16').max

    if (
        max_dense > min_f16 and max_dense < max_f16 and
        min_dense > min_f16 and min_dense < max_f16
    ):
        tile_data['dense'] = base64.b64encode(tile.astype('float16')).decode('latin-1')
        tile_data['dtype'] = 'float16'
    else:
        tile_data['dense'] = base64.b64encode(tile.astype('float32')).decode('latin-1')
        tile_data['dtype'] = 'float32'

    return tile_data


def extract_tileset_uid(tile_id):
    '''
    Get the tileset uid from a tile id. Should usually be all the text
    before the first dot.

    Parameters
    ----------
    tile_id : str
        The id of the tile we're getting the tileset info for (e.g. xyz.0.0.1)
    Returns
    -------
    tileset_uid : str
        The uid of the tileset that this tile comes from
    '''
    tile_id_parts = tile_id.split('.')
    tileset_uuid = tile_id_parts[0]

    return tileset_uuid

def generate_hitile_tiles(tileset, tile_ids):
    '''
    Generate tiles from a hitile file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:3]))

        dense = hdft.get_data(
            h5py.File(
                get_datapath(tileset.datafile.url)
            ),
            tile_position[0],
            tile_position[1]
        )

        if len(dense):
            max_dense = max(dense)
            min_dense = min(dense)
        else:
            max_dense = 0
            min_dense = 0

        min_f16 = np.finfo('float16').min
        max_f16 = np.finfo('float16').max

        has_nan = len([d for d in dense if np.isnan(d)]) > 0

        if (
            not has_nan and
            max_dense > min_f16 and max_dense < max_f16 and
            min_dense > min_f16 and min_dense < max_f16
        ):
            tile_value = {
                'dense': base64.b64encode(dense.astype('float16')).decode('utf-8'),
                'dtype': 'float16'
            }
        else:
            tile_value = {
                'dense': base64.b64encode(dense.astype('float32')).decode('utf-8'),
                'dtype': 'float32'
            }

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def generate_beddb_tiles(tileset, tile_ids):
    '''
    Generate tiles from a beddb file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []

    for tile_id in tile_ids:
        tile_position = list(map(int, tile_id_parts[1:3]))
        tile_value = cdt.get_tile(
            get_datapath(tileset.datafile.url),
            tile_position[0],
            tile_position[1]
        )

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def generate_bed2ddb_tiles(tileset, tile_ids):
    '''
    Generate tiles from a bed2db file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []

    for tile_id in tile_ids:
        tile_position = list(map(int, tile_id_parts[1:4]))
        tile_value = cdt.get_2d_tile(
            get_datapath(tileset.datafile.url),
            tile_position[0],
            tile_position[1],
            tile_position[2]
        )

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def generate_hibed_tiles(tileset, tile_ids):
    '''
    Generate tiles from a hibed file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []
    for tile_id in tile_ds:
        tile_position = list(map(int, tile_id_parts[1:3]))
        dense = hdft.get_discrete_data(
            h5py.File(
                get_datapath(tileset.datafile.url)
            ),
            tile_position[0],
            tile_position[1]
        )

        tile_value = {'discrete': list([list([x.decode('utf-8') for x in d]) for d in dense])}

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def bin_tiles_by_zoom_level_and_transform(tile_ids):
    '''
    Place these tiles into separate lists according to their
    zoom level and transform type

    Parameters
    ----------
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_lists: [tile_ids, tile_ids]
        A list of lists of tiles each of which have the same zoom level
        and transform type
    '''
    tile_id_lists = col.defaultdict(set)

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:4]))
        zoom_level = tile_position[0]

        if len(tile_id_parts) > 4:
            transform_method = tile_id_parts[4]
        else:
            transform_method = 'default'

        tile_id_lists[(zoom_level, transform_method)].add(tile_id)

    return tile_id_lists

def partition_to_adjacent_tiles(tile_ids):
    '''
    Partition a set of tile ids into sets of adjacent tiles

    Parameters
    ----------
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_lists: [tile_ids, tile_ids]
        A list of tile lists, all of which have tiles that
        are within 1 position of another tile in the list
    '''
    tile_id_lists = []

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')

        # exclude the zoom level in the position
        # because the tiles should already have been partitioned
        # by zoom level
        tile_position = list(map(int, tile_id_parts[2:4]))

        added = False

        for tile_id_list in tile_id_lists:
            far_apart = False

            for ct_tile_id in tile_id_list:
                ct_tile_id_parts = ct_tile_id.split('.')
                ct_tile_position = list(map(int, tile_id_parts[1:4]))

                for p1,p2 in zip(tile_position, ct_tile_position):
                    if abs(int(p1) - int(p2)) >= 1:
                        # too far apart can't be part of the same group
                        far_apart = True

                if not far_apart:
                    tile_id_list += [tile_id]
                    added = True
                    break
                
            if added:
                break
        if not added:
            tile_id_lists += [[tile_id]]

    return tile_id_lists

def generate_cooler_tiles(tileset, tile_ids):
    '''
    Generate tiles from a cooler file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    tile_ids_by_zoom_and_transform = bin_tiles_by_zoom_level_and_transform(tile_ids)
    print("tile_ids_by_zoom_and_transform:", tile_ids_by_zoom_and_transform)

    print("gct tile_ids:", tile_ids)
    tile_position = list(map(int, tile_id_parts[1:4]))

    if len(tile_id_parts) > 4:
        transform_method = tile_id_parts[4]
    else:
        transform_method = 'default'
    
    tile_value = make_cooler_tile(
        get_datapath(tileset.datafile.url), tile_position,
        transform_method
    )
    if tile_value is None:
        return None
    
def generate_tiles(tileset, tile_ids):
    '''
    Generate a tiles for the give tile_ids.

    All of the tile_ids must come from the same tileset. This function
    will determine the appropriate handler this tile given the tileset's
    filetype and datatype

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''

    if tileset.filetype == 'hitile':
        return generate_hitile_tiles(tileset, tile_ids)
    elif tileset.filetype == 'beddb':
        return generate_beddb_tiles(tileset, tile_ids)
    elif tileset.filetype == 'bed2db':
        generate_bed2ddb_tiles(tileset, tile_ids)
    elif tileset.filetype == 'hibed':
        return generate_hibed_tiles(tileset, tile_ids)
    elif tileset.filetype == 'cooler':
        return generate_cooler_tiles(tileset, tile_ids)
    else:
        raise("Unknown tileset type:", tileset.filetype)

def generate_tile(tile_id, request):
    '''
    Create a tile. The tile_id specifies the dataset as well
    as the position.

    This function will look at the filetype and determine what type
    of tile to retrieve (e..g cooler -> 2D dense, hitile -> 1D dense,
    elasticsearch -> anything)

    Args:
        tile_id (str): The id of a tile, consisting of the tileset id,
            followed by the tile position (e.g. PIYqJpdyTCmAZGmA6jNHJw.4.0.0)
        request (django.http.HTTPRequest): The request that included this tile.

    Returns:
        (string, dict): A tuple containing the tile ID tile data
    '''

    tileset_uuid = extract_tileset_uid(tile_id)
    tile_id_parts = tile_id.split('.')

    tileset = tm.Tileset.objects.get(uuid=tileset_uuid)

    if tileset.private and request.user != tileset.owner:
        # dataset is not public return an empty set
        return (tileset_uuid, {'error': "Forbidden"})

    tile_value = rdb.get(tile_id)

    if tile_value is not None:
        tile_value = pickle.loads(tile_value)
        return (tile_id, tile_value)

    if tileset.filetype == "hitile":
        tile_position = list(map(int, tile_id_parts[1:3]))

        dense = hdft.get_data(
            h5py.File(
                get_datapath(tileset.datafile.url)
            ),
            tile_position[0],
            tile_position[1]
        )

        if len(dense):
            max_dense = max(dense)
            min_dense = min(dense)
        else:
            max_dense = 0
            min_dense = 0

        min_f16 = np.finfo('float16').min
        max_f16 = np.finfo('float16').max

        has_nan = len([d for d in dense if np.isnan(d)]) > 0

        if (
            not has_nan and
            max_dense > min_f16 and max_dense < max_f16 and
            min_dense > min_f16 and min_dense < max_f16
        ):
            tile_value = {
                'dense': base64.b64encode(dense.astype('float16')).decode('utf-8'),
                'dtype': 'float16'
            }
        else:
            tile_value = {
                'dense': base64.b64encode(dense.astype('float32')).decode('utf-8'),
                'dtype': 'float32'
            }

    elif tileset.filetype == 'beddb':
        tile_position = list(map(int, tile_id_parts[1:3]))
        tile_value = cdt.get_tile(
            get_datapath(tileset.datafile.url),
            tile_position[0],
            tile_position[1]
        )

    elif tileset.filetype == 'bed2ddb':
        tile_position = list(map(int, tile_id_parts[1:4]))
        tile_value = cdt.get_2d_tile(
            get_datapath(tileset.datafile.url),
            tile_position[0],
            tile_position[1],
            tile_position[2]
        )

    elif tileset.filetype == 'hibed':
        tile_position = list(map(int, tile_id_parts[1:3]))
        dense = hdft.get_discrete_data(
            h5py.File(
                get_datapath(tileset.datafile.url)
            ),
            tile_position[0],
            tile_position[1]
        )

        tile_value = {'discrete': list([list([x.decode('utf-8') for x in d]) for d in dense])}
    elif tileset.filetype == "cooler":
        tile_position = list(map(int, tile_id_parts[1:4]))


        if len(tile_id_parts) > 4:
            transform_method = tile_id_parts[4]
        else:
            transform_method = 'default'
        
        tile_value = make_cooler_tile(
            get_datapath(tileset.datafile.url), tile_position,
            transform_method
        )
        if tile_value is None:
            return None

    rdb.set(tile_id, pickle.dumps(tile_value))
    return (tile_id, tile_value)


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = tss.UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = tss.UserSerializer

@api_view(['GET'])
def uids_by_filename(request):
    '''
    Retrieve a list uids corresponding to a given filename
    '''
    queryset = tm.Tileset.objects.all()
    queryset = queryset.filter(datafile__contains=request.GET['d'])

    serializer = tss.UserFacingTilesetSerializer(queryset, many=True)

    return JsonResponse({"count": len(queryset), "results": serializer.data})

@api_view(['GET'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def available_chrom_sizes(request):
    '''
    Get the list of available chromosome size lists.

    Args:
        request: HTTP GET request object. Should contain no query features

    Returns:
        A JSON response containing the list of chromosome size lists.
    '''
    queryset = tm.Tileset.objects.all()
    queryset = queryset.filter(datatype__in=["chromsizes"])

    serializer = tss.UserFacingTilesetSerializer(queryset, many=True)

    return JsonResponse({"count": len(queryset), "results": serializer.data})


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
        chrom_sizes = tm.Tileset.objects.get(uuid=uuid)
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
        f.open('r')

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


@api_view(['GET'])
def suggest(request):
    '''
    Suggest gene names based on the input text
    '''
    # suggestions are taken from a gene annotations tileset
    tileset_uuid = request.GET['d']
    text = request.GET['ac']

    try:
        tileset = tm.Tileset.objects.get(uuid=tileset_uuid)
    except ObjectDoesNotExist:
        raise rfe.NotFound('Suggestion source file not found')

    result_dict = tsu.get_gene_suggestions(
        get_datapath(tileset.datafile.url), text
    )

    return JsonResponse(result_dict, safe=False)


@api_view(['GET', 'POST'])
def viewconfs(request):
    '''
    Retrieve a viewconfs with a given uid

    Args:

    request (django.http.HTTPRequest): The request object containing the
        uid (e.g. d=hg45ksdjfds) that identifies the viewconf.

    Return:

    '''
    if request.method == 'POST':
        if not hss.UPLOAD_ENABLED:
            return JsonResponse({
                'error': 'Uploads disabled'
            }, status=403)

        if request.user.is_anonymous() and not hss.PUBLIC_UPLOAD_ENABLED:
            return JsonResponse({
                'error': 'Public uploads disabled'
            }, status=403)

        #print("request.body:", request.body)
        viewconf_wrapper = json.loads(request.body)
        uid = viewconf_wrapper.get('uid') or slugid.nice().decode('utf-8')

        try:
            viewconf = json.dumps(viewconf_wrapper['viewconf'])
        except KeyError:
            return JsonResponse({
                'error': 'Broken view config'
            }, status=400)

        try:
            higlass_version = viewconf_wrapper['higlassVersion']
        except KeyError:
            higlass_version = ''

        serializer = tss.ViewConfSerializer(data={'viewconf': viewconf})

        if not serializer.is_valid():
            return JsonResponse({
                'error': 'Serializer not valid'
            }, status=rfs.HTTP_400_BAD_REQUEST)

        serializer.save(
            uuid=uid, viewconf=viewconf, higlassVersion=higlass_version
        )

        return JsonResponse({'uid': uid})

    uid = request.GET.get('d')

    if not uid:
        return JsonResponse({
            'error': 'View config ID not specified'
        }, status=404)

    try:
        obj = tm.ViewConf.objects.get(uuid=uid)
    except ObjectDoesNotExist:
        return JsonResponse({
            'error': 'View config not found'
        }, status=404)

    return JsonResponse(json.loads(obj.viewconf))


@api_view(['GET'])
def tiles(request):
    '''Retrieve a set of tiles

    A call to this API function should retrieve a few tiles.

    Args:
        request (django.http.HTTPRequest): The request object containing
            the parameters (e.g. d=x.0.0) that identify the tiles being
            requested.

    Returns:
        django.http.JsonResponse: A JSON object containing all of the tile
            data being requested. The JSON object is just a dictionary of
            (tile_id, tile_data) items.

    '''

    global mats

    # create a set so that we don't fetch the same tile multiple times
    tileids_to_fetch = set(request.GET.getlist("d"))
    # with ProcessPoolExecutor() as executor:
    # 	  res = executor.map(parallelize, hargs)
    '''
    p = mp.Pool(4)
    res = p.map(parallelize, hargs)
    '''

    tileids_by_tileset = col.defaultdict(set)
    generated_tiles = []

    # sort tile_ids by the dataset they come from
    for tile_id in tileids_to_fetch:
        # see if the tile is cached
        tile_value = rdb.get(tile_id)

        if tile_value is not None:
            # we found the tile in the cache, no need to fetch it again
            tile_value = pickle.loads(tile_value)
            generated_tiles += [(tile_id, tile_value)]
            continue
            
        tileset_uuid = extract_tileset_uid(tile_id)
        tileids_by_tileset[tileset_uuid].add(tile_id)

    print('tileids_to_fetch', tileids_to_fetch)
    print('tileids_by_tileset:', tileids_by_tileset)

    # fetch the tiles
    for tileset_uuid in tileids_by_tileset:
        # load the tileset object
        tileset = tm.Tileset.objects.get(uuid=tileset_uuid)

        # check permissions
        if tileset.private and request.user != tileset.owner:
            generated_tiles += [(tile_id, {'error': "Forbidden"}) for tile_id in tileids_by_tileset[tileset_uuid]]
        else:
            generated_tiles += generate_tiles(tileset, tileids_by_tileset[tileset_uuid])

    res = map(lambda x: generate_tile(x, request), tileids_to_fetch)

    #print("res:", res)

    # create a dictionary of tileids
    result_dict = dict([i for i in res if i is not None])

    return JsonResponse(result_dict, safe=False)


def get_datapath(relpath):
    return op.join(hss.BASE_DIR, relpath)


@api_view(['GET'])
def tileset_info(request):
    ''' Get information about a tileset

    Tilesets have information critical to their display
    such as the maximum number of dimensions and well as
    their width. This needs to be relayed to the client
    in order for it to know which tiles to request.

    Args:
        request (django.http.HTTPRequest): The request object
            containing tileset_ids in the 'd' parameter.
    Return:
        django.http.JsonResponse: A JSON object containing
            the tileset meta-information
    '''
    global mats
    queryset = tm.Tileset.objects.all()
    tileset_uuids = request.GET.getlist("d")
    tileset_infos = {}
    for tileset_uuid in tileset_uuids:
        tileset_object = queryset.filter(uuid=tileset_uuid).first()

        if tileset_object is None:
            tileset_infos[tileset_uuid] = {
                'error': 'No such tileset with uid: {}'.format(tileset_uuid)
            }
            continue

        if tileset_object.private and request.user != tileset_object.owner:
            # dataset is not public
            tileset_infos[tileset_uuid] = {'error': "Forbidden"}
            continue

        if (
            tileset_object.filetype == 'hitile' or
            tileset_object.filetype == 'hibed'
        ):
            tileset_info = hdft.get_tileset_info(
                h5py.File(get_datapath(tileset_object.datafile.url)))
            tileset_infos[tileset_uuid] = {
                "min_pos": [int(tileset_info['min_pos'])],
                "max_pos": [int(tileset_info['max_pos'])],
                "max_width": 2 ** math.ceil(
                    math.log(
                        tileset_info['max_pos'] - tileset_info['min_pos']
                    ) / math.log(2)
                ),
                "tile_size": int(tileset_info['tile_size']),
                "max_zoom": int(tileset_info['max_zoom'])
            }
        elif tileset_object.filetype == "elastic_search":
            response = urllib.urlopen(
                tileset_object.datafile + "/tileset_info")
            tileset_infos[tileset_uuid] = json.loads(response.read())
        elif tileset_object.filetype == 'beddb':
            tileset_infos[tileset_uuid] = cdt.get_tileset_info(
                get_datapath(tileset_object.datafile.url)
            )
        elif tileset_object.filetype == 'bed2ddb':
            tileset_infos[tileset_uuid] = cdt.get_2d_tileset_info(
                get_datapath(tileset_object.datafile.url)
            )
        elif tileset_object.filetype == 'cooler':
            dsetname = get_datapath(queryset.filter(
                uuid=tileset_uuid
            ).first().datafile.url)

            if dsetname not in mats:
                make_mats(dsetname)
            tileset_infos[tileset_uuid] = mats[dsetname][1]
        else:
            # Unknown filetype
            tileset_infos[tileset_uuid] = {
                'message': 'Unknown filetype ' + tileset_object.filetype
            }

        tileset_infos[tileset_uuid]['name'] = tileset_object.name
        tileset_infos[tileset_uuid]['coordSystem'] = tileset_object.coordSystem
        tileset_infos[tileset_uuid]['coordSystem2'] =\
            tileset_object.coordSystem2

    '''
    for info in tileset_infos.values():
        print('info:', info, type(info['max_width']), [type(x) for x in info['max_pos']], [type(x) for x in info['min_pos']], type(info['tile_size']), type(info['max_zoom']))
    '''

    return JsonResponse(tileset_infos)


@method_decorator(gzip_page, name='dispatch')
class TilesetsViewSet(viewsets.ModelViewSet):
    """Tilesets"""

    queryset = tm.Tileset.objects.all()
    serializer_class = tss.TilesetSerializer

    if hss.UPLOAD_ENABLED:
        permission_classes = (tsp.UserPermission,)
    else:
        permission_classes = (tsp.UserPermissionReadOnly,)

    lookup_field = 'uuid'
    parser_classes = (rfp.MultiPartParser,)

    def list(self, request, *args, **kwargs):
        '''List the available tilesets

        Args:
            request (django.http.HTTPRequest): The HTTP request containing
                no parameters

        Returns:
            django.http.JsonResponse: A json file containing a 'count' as
                well as 'results' with each tileset as an entry
        '''
        # only return tilesets which are accessible by this user
        if request.user.is_anonymous:
            user = gu.get_anonymous_user()
        else:
            user = request.user

        queryset = self.queryset.filter(
            dbm.Q(owner=user) | dbm.Q(private=False)
        )

        if 'ac' in request.GET:
            # Autocomplete fields
            queryset = queryset.filter(name__contains=request.GET['ac'])
        if 't' in request.GET:
            # Filter by filetype
            queryset = queryset.filter(filetype=request.GET['t'])
        if 'dt' in request.GET:
            # Filter by datatype
            queryset = queryset.filter(datatype__in=request.GET.getlist('dt'))

        if 'o' in request.GET:
            if 'r' in request.GET:
                queryset = queryset.order_by(dbmf.Lower(request.GET['o']).desc())
            else:
                queryset = queryset.order_by(dbmf.Lower(request.GET['o']).asc())

        #ts_serializer = tss.UserFacingTilesetSerializer(queryset, many=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ts_serializer(queryset, many=True)
        return JsonResponse(serializer.data)

        """
        return JsonResponse(
            {"count": len(queryset), "results": ts_serializer.data}
        )
        """

    def perform_create(self, serializer):
        '''Add a new tileset

        When adding a new dataset, we need to enforce permissions as well as
        other rules like the uniqueness of uuids.

        Args:
            serializer (tilsets.serializer.TilesetSerializer): The serializer
            to use to save the request.
        '''

        if 'uid' in self.request.data:
            try:
                self.queryset.get(uuid=self.request.data['uid'])
                # this uid already exists, return an error
                raise rfe.APIException("UID already exists")
            except tm.Tileset.DoesNotExist:
                uid = self.request.data['uid']
        else:
            uid = slugid.nice().decode('utf-8')

        if 'filetype' not in self.request.data:
            raise rfe.APIException('Missing filetype')

        datafile_name = self.request.data.get('datafile').name

        if 'name' in self.request.data:
            name = self.request.data['name']
        else:
            name = op.split(datafile_name)[1]

        if self.request.user.is_anonymous:
            # can't create a private dataset as an anonymous user
            serializer.save(
                owner=gu.get_anonymous_user(),
                private=False,
                name=name,
                uuid=uid
            )
        else:
            serializer.save(owner=self.request.user, name=name, uuid=uid)
