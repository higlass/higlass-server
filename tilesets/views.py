# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import h5py
import json
import logging
import math

import clodius.db_tiles as cdt
import clodius.hdf_tiles as hdft

import collections as col

import django.db.models as dbm
import django.db.models.functions as dbmf

import guardian.utils as gu

import higlass_server.settings as hss
import itertools as it

import tilesets.chromsizes as tcs
import tilesets.generate_tiles as tgt
import tilesets.models as tm
import tilesets.permissions as tsp
import tilesets.serializers as tss
import tilesets.suggestions as tsu
import tilesets.utils as tut

import os.path as op

import rest_framework.exceptions as rfe
import rest_framework.parsers as rfp
import rest_framework.status as rfs

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

from higlass_server.utils import getRdb

logger = logging.getLogger(__name__)

rdb = getRdb()

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
            type: return data format [csv, tsv, or json]
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
        err_msg = 'Oh lord! ChromSizes for %s not found. 😬' % uuid
        err_status = 404

        if is_json:
            return response({'error': err_msg}, status=err_status)

        return response(err_msg, status=err_status)

    # Try to load the chromosome sizes and return them as a list of 
    # (name, size) tuples
    try:
        if chrom_sizes.filetype == 'cooler':
            data = tcs.get_cooler_chromsizes(tut.get_datapath(chrom_sizes.datafile.url))
        else:
            data = tcs.get_tsv_chromsizes(tut.get_datapath(chrom_sizes.datafile.url))
    except Exception as ex:
        err_msg = str(ex)
        err_status = 500

        if is_json:
            return response({'error': err_msg}, status=err_status)

        return response(err_msg, status=err_status)

    # Convert the stuff if needed
    try:
        # data should be a list of (name, size) tuples coming
        # coming and converted to a more appropriate data type
        # going out
        if res_type == 'tsv':
            lines = []
            for (name, size) in data:
                lines += ["{}\t{}".format(name, size)]
                data = lines

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
        tut.get_datapath(tileset.datafile.url), text
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

        if request.user.is_anonymous and not hss.PUBLIC_UPLOAD_ENABLED:
            return JsonResponse({
                'error': 'Public uploads disabled'
            }, status=403)

        viewconf_wrapper = json.loads(request.body.decode('utf-8'))
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

        existing_object = tm.ViewConf.objects.filter(uuid=uid)
        if len(existing_object) > 0:
            return JsonResponse({
                'error': 'Object with uid {} already exists'.format(uid)
            }, status=rfs.HTTP_400_BAD_REQUEST);

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

def add_transform_type(tile_id):
    '''
    Add a transform type to a cooler tile id if it's not already
    present.

    Parameters
    ----------
    tile_id: str
        A tile id (e.g. xyz.0.1.0)

    Returns
    -------
    new_tile_id: str
        A formatted tile id, potentially with an added transform_type
    '''
    tile_id_parts = tile_id.split('.')
    tileset_uuid = tile_id_parts[0]
    tile_position = tile_id_parts[1:4]

    transform_type = tgt.get_transform_type(tile_id)
    new_tile_id = ".".join([tileset_uuid] + tile_position + [transform_type])
    return new_tile_id

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

    tilesets = {}
    transform_id_to_original_id = {}

    # sort tile_ids by the dataset they come from
    for tile_id in tileids_to_fetch:
        tileset_uuid = tgt.extract_tileset_uid(tile_id)

        # get the tileset object first
        if tileset_uuid in tilesets:
            tileset = tilesets[tileset_uuid]
        else:
            tileset = tm.Tileset.objects.get(uuid=tileset_uuid)
            tilesets[tileset_uuid] = tileset

        if tileset.filetype == 'cooler':
            # cooler tiles can have a transform (e.g. 'ice', 'kr') which
            # needs to be added if it's not there (e.g. 'default')
            new_tile_id = add_transform_type(tile_id)
            transform_id_to_original_id[new_tile_id] = tile_id
            tile_id = new_tile_id
        else:
            transform_id_to_original_id[tile_id] = tile_id

        # see if the tile is cached
        tile_value = None
        try:
            tile_value = rdb.get(tile_id)
        except Exception as ex:
            # there was an error accessing the cache server
            # log the error and carry forward fetching the tile
            # from the original data
            logger.error(ex)
            
        #tile_value = None

        if tile_value is not None:
            # we found the tile in the cache, no need to fetch it again
            tile_value = pickle.loads(tile_value)
            generated_tiles += [(tile_id, tile_value)]
            continue

        tileids_by_tileset[tileset_uuid].add(tile_id)

    # fetch the tiles
    tilesets = [tilesets[tu] for tu in tileids_by_tileset]
    accessible_tilesets = [(t, tileids_by_tileset[t.uuid]) for t in tilesets if ((not t.private) or request.user == t.owner)]

    #pool = mp.Pool(6)

    generated_tiles += list(it.chain(*map(tgt.generate_tiles, accessible_tilesets)))

    '''
    for tileset_uuid in tileids_by_tileset:
        # load the tileset object
        tileset = tilesets[tileset_uuid]

        # check permissions
        if tileset.private and request.user != tileset.owner:
            generated_tiles += [(tile_id, {'error': "Forbidden"}) for tile_id in tileids_by_tileset[tileset_uuid]]
        else:
            generated_tiles += generate_tiles(tileset, tileids_by_tileset[tileset_uuid])
    '''

    # store the tiles in redis

    tiles_to_return = {}

    for (tile_id, tile_value) in generated_tiles:
        try:
            rdb.set(tile_id, pickle.dumps(tile_value))
        except Exception as ex:
            # error caching a tile
            # log the error and carry forward, this isn't critical
            logger.error(ex)

        if tile_id in transform_id_to_original_id:
            original_tile_id = transform_id_to_original_id[tile_id]
        else:
            # not in our list of reformatted tile ids, so it probably
            # wasn't requested
            continue

        if original_tile_id in tileids_to_fetch:
            tiles_to_return[original_tile_id] = tile_value

    return JsonResponse(tiles_to_return, safe=False)

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
                h5py.File(tut.get_datapath(tileset_object.datafile.url), 'r'))
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
        elif tileset_object.filetype == 'bigwig':
            tileset_infos[tileset_uuid] = tgt.generate_bigwig_tileset_info(tileset_object)
        elif tileset_object.filetype == 'multivec':
            tileset_infos[tileset_uuid] = tgt.generate_multivec_tileset_info(
                    tut.get_datapath(tileset_object.datafile.url))
        elif tileset_object.filetype == "elastic_search":
            response = urllib.urlopen(
                tileset_object.datafile + "/tileset_info")
            tileset_infos[tileset_uuid] = json.loads(response.read())
        elif tileset_object.filetype == 'beddb':
            tileset_infos[tileset_uuid] = cdt.get_tileset_info(
                tut.get_datapath(tileset_object.datafile.url)
            )
        elif tileset_object.filetype == 'bed2ddb':
            tileset_infos[tileset_uuid] = cdt.get_2d_tileset_info(
                tut.get_datapath(tileset_object.datafile.url)
            )
        elif tileset_object.filetype == 'cooler':
            dsetname = tut.get_datapath(queryset.filter(
                uuid=tileset_uuid
            ).first().datafile.url)

            if dsetname not in tgt.mats:
                tgt.make_mats(dsetname)
            tileset_infos[tileset_uuid] = tgt.mats[dsetname][1]
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
