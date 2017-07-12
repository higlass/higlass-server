# -*- coding: utf-8 -*-
from __future__ import print_function

import base64
import csv
import clodius.hdf_tiles as hdft
import clodius.db_tiles as cdt
import django.db.models as dbm
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
from tiles import make_tile

from higlass_server.utils import getRdb

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

logger = logging.getLogger(__name__)

global mats
mats = {}

rdb = getRdb()


def make_mats(dset):
    f = h5py.File(dset, 'r')
    mats[dset] = [f, cch.get_info(dset)]


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

    tile = make_tile(
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
        tile_data['dense'] = base64.b64encode(tile.astype('float16'))
        tile_data['dtype'] = 'float16'
    else:
        tile_data['dense'] = base64.b64encode(tile.astype('float32'))
        tile_data['dtype'] = 'float32'

    return tile_data


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

    tile_id_parts = tile_id.split('.')
    tileset_uuid = tile_id_parts[0]

    tileset = tm.Tileset.objects.get(uuid=tileset_uuid)

    if tileset.private and request.user != tileset.owner:
        # dataset is not public return an empty set
        return (tileset_uuid, {'error': "Forbidden"})

    tile_value = rdb.get(tile_id)

    if tile_value is not None:
        tile_value = pickle.loads(tile_value)
        return (tile_id, tile_value)

    if tileset.filetype == "hitile":
        tile_position = map(int, tile_id_parts[1:3])

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

        if (
            max_dense > min_f16 and max_dense < max_f16 and
            min_dense > min_f16 and min_dense < max_f16
        ):
            tile_value = {
                'dense': base64.b64encode(dense.astype('float16')),
                'dtype': 'float16'
            }
        else:
            tile_value = {
                'dense': base64.b64encode(dense.astype('float32')),
                'dtype': 'float32'
            }

    elif tileset.filetype == 'beddb':
        tile_position = map(int, tile_id_parts[1:3])
        tile_value = cdt.get_tile(
            get_datapath(tileset.datafile.url),
            tile_position[0],
            tile_position[1]
        )

    elif tileset.filetype == 'bed2ddb':
        tile_position = map(int, tile_id_parts[1:4])
        tile_value = cdt.get_2d_tile(
            get_datapath(tileset.datafile.url),
            tile_position[0],
            tile_position[1],
            tile_position[2]
        )

    elif tileset.filetype == 'hibed':
        tile_position = map(int, tile_id_parts[1:3])
        dense = hdft.get_discrete_data(
            h5py.File(
                get_datapath(tileset.datafile.url)
            ),
            tile_position[0],
            tile_position[1]
        )

        tile_value = {'discrete': list([list(d) for d in dense])}
    elif tileset.filetype == "cooler":
        tile_position = map(int, tile_id_parts[1:4])

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

        viewconf_wrapper = json.loads(request.body)
        uid = viewconf_wrapper.get('uid') or slugid.nice()

        try:
            viewconf = json.dumps(viewconf_wrapper['viewconf'])
        except KeyError:
            return JsonResponse({
                'error': 'Broken view config'
            }, status=400)

        try:
            higlass_version = viewconf_wrapper['higlassVersion']
            print(higlass_version)
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

    res = map(lambda x: generate_tile(x, request), tileids_to_fetch)

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
                "min_pos": [tileset_info['min_pos']],
                "max_pos": [tileset_info['max_pos']],
                "max_width": 2 ** math.ceil(
                    math.log(
                        tileset_info['max_pos'] - tileset_info['min_pos']
                    ) / math.log(2)
                ),
                "tile_size": tileset_info['tile_size'],
                "max_zoom": tileset_info['max_zoom']
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

    return JsonResponse(tileset_infos)

@method_decorator(gzip_page, name="dispatch")
class ViewConfViewSet(viewsets.ModelViewSet):
    """
    Viewconfs
    """
    queryset = tm.ViewConf.objects.all()
    serliazer_class = tss.ViewConfSerializer

    lookup_field = 'uuid'
    parser_classes = (rfp.JSONParser,)

    if hss.UPLOAD_ENABLED:
        permission_classes = (tsp.UserPermission,)
    else:
        permission_classes = (tsp.UserPermissionReadOnly,)

    def list(self, request, *args, **kwargs):
        '''List the available viewconfs

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
            uid = slugid.nice()

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
            # order by a field
            if 'r' in request.GET:
                # reverse the ordering
                queryset = queryset.order_by('-' + request.GET['o'])
            else:
                queryset = queryset.order_by(request.GET['o'])

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
        if request.user.is_anonymous() and not hss.PUBLIC_UPLOAD_ENABLED:
            return JsonResponse({
                'error': 'Public uploads disabled'
            }, status=403)

        viewconf_wrapper = json.loads(self.request.body)
        uid = viewconf_wrapper.get('uid') or slugid.nice()

        try:
            viewconf = json.dumps(viewconf_wrapper['viewconf'])
        except KeyError:
            return JsonResponse({
                'error': 'Broken view config'
            }, status=400)

        try:
            higlass_version = viewconf_wrapper['higlassVersion']
            print(higlass_version)
        except KeyError:
            higlass_version = ''

        if not serializer.is_valid():
            return JsonResponse({
                'error': 'Serializer not valid'
            }, status=rfs.HTTP_400_BAD_REQUEST)

        serializer.save(
            uuid=uid, viewconf=viewconf, higlassVersion=higlass_version
        )

        return JsonResponse({'uid': uid})
