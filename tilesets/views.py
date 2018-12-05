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
import django.core.exceptions as dce
import django.http as dh

import guardian.utils as gu

import higlass_server.settings as hss
import itertools as it

import tilesets.chromsizes as tcs
import tilesets.generate_tiles as tgt
import tilesets.multivec_tiles as tmt

import clodius.tiles.cooler as hgco
import clodius.tiles.bigwig as hgbi
import clodius.tiles.multivec as hgmu
import clodius.tiles.time_interval as hgti
import clodius.tiles.geo as hggo
import clodius.tiles.imtiles as hgim

import tilesets.chromsizes as tcs
import tilesets.models as tm
import tilesets.permissions as tsp
import tilesets.serializers as tss
import tilesets.suggestions as tsu

from tilesets.management.commands.ingest_tileset import ingest as ingest_tileset_to_db

import os
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
        logger.exception(e)
        err_msg = 'Oh lord! ChromSizes for %s not found. 😬' % uuid
        err_status = 404

        if is_json:
            return response({'error': err_msg}, status=err_status)

        return response(err_msg, status=err_status)

    # Try to load the chromosome sizes and return them as a list of
    # (name, size) tuples
    try:
        if tgt.get_tileset_filetype(chrom_sizes) == 'bigwig':
            data = hgbi.chromsizes(chrom_sizes.datafile.path)
        elif tgt.get_tileset_filetype(chrom_sizes) == 'cooler':
            data = tcs.get_cooler_chromsizes(chrom_sizes.datafile.path)
        elif tgt.get_tileset_filetype(chrom_sizes) == 'chromsizes-tsv':
            data = tcs.get_tsv_chromsizes(chrom_sizes.datafile.path)
        elif tgt.get_tileset_filetype(chrom_sizes) == 'multivec':
            data = tcs.get_multivec_chromsizes(chrom_sizes.datafile.path)
        else:
            data = '';

    except Exception as ex:
        logger.exception(ex)
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
                lines += ["{}\t{}\n".format(name, size)]
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
        logger.exception(e)
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
        tileset.datafile.path, text
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

    transform_type = hgco.get_transform_type(tile_id)
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
    #       res = executor.map(parallelize, hargs)
    '''
    p = mp.Pool(4)
    res = p.map(parallelize, hargs)
    '''

    # Return the raw data if only one tile is requested. This currently only
    # works for `imtiles`
    raw = request.GET.get('raw', False)

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
    accessible_tilesets = [(t, tileids_by_tileset[t.uuid], raw) for t in tilesets if ((not t.private) or request.user == t.owner)]

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

    if len(generated_tiles) == 1 and raw and 'image' in generated_tiles[0][1]:
        return HttpResponse(
            generated_tiles[0][1]['image'], content_type='image/jpeg'
        )

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

    chromsizes_error = None

    if 'cs' in request.GET:
        # we need to call a different server to get the tiles
        if not 'ci' in request.GET.getlist:
            chromsizes_error = 'cs param present without ci'

        # call the request server and get the chromsizes
        pass
    else:
        if 'ci' in request.GET:
            try:
                chromsizes = tm.Tileset.objects.get(uuid=request.GET['ci'])
                data = tcs.chromsizes_array_to_series(
                        tcs.get_tsv_chromsizes(chromsizes.datafile.path))
            except Exception as ex:
                pass

    for tileset_uuid in tileset_uuids:
        tileset_object = queryset.filter(uuid=tileset_uuid).first()

        if tileset_uuid == 'osm-image':
            tileset_infos[tileset_uuid] = {
                'min_x': 0,
                'max_height': 134217728,
                'min_y': 0,
                'max_y': 134217728,
                'max_zoom': 19,
                'tile_size': 256
            }
            continue

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
                h5py.File(tileset_object.datafile.path, 'r'))
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
            chromsizes = tgt.get_chromsizes(tileset_object)
            tsinfo = hgbi.tileset_info(
                    tileset_object.datafile.path,
                    chromsizes
                )
            #print('tsinfo:', tsinfo)
            if 'chromsizes' in tsinfo:
                tsinfo['chromsizes'] = [(c, int(s)) for c,s in tsinfo['chromsizes']]
            tileset_infos[tileset_uuid] = tsinfo
        elif tileset_object.filetype == 'multivec':
            tileset_infos[tileset_uuid] = hgmu.tileset_info(
                    tileset_object.datafile.path)
        elif tileset_object.filetype == "elastic_search":
            response = urllib.urlopen(
                tileset_object.datafile + "/tileset_info")
            tileset_infos[tileset_uuid] = json.loads(response.read())
        elif tileset_object.filetype == 'beddb':
            tileset_infos[tileset_uuid] = cdt.get_tileset_info(
                tileset_object.datafile.path
            )
        elif tileset_object.filetype == 'bed2ddb':
            tileset_infos[tileset_uuid] = cdt.get_2d_tileset_info(
                tileset_object.datafile.path
            )
        elif tileset_object.filetype == 'cooler':
            tileset_infos[tileset_uuid] = hgco.tileset_info(
                    tileset_object.datafile.path
            )
        elif tileset_object.filetype == 'time-interval-json':
            tileset_infos[tileset_uuid] = hgti.tileset_info(
                    tileset_object.datafile.path
            )
        elif (
            tileset_object.filetype == '2dannodb' or
            tileset_object.filetype == 'imtiles'
        ):
            tileset_infos[tileset_uuid] = hgim.get_tileset_info(
                tileset_object.datafile.path
            )
        elif tileset_object.filetype == 'geodb':
            tileset_infos[tileset_uuid] = hggo.tileset_info(
                tileset_object.datafile.path
            )
        else:
            # Unknown filetype
            tileset_infos[tileset_uuid] = {
                'error': 'Unknown filetype ' + tileset_object.filetype
            }

        tileset_infos[tileset_uuid]['name'] = tileset_object.name
        tileset_infos[tileset_uuid]['datatype'] = tileset_object.datatype
        tileset_infos[tileset_uuid]['coordSystem'] = tileset_object.coordSystem
        tileset_infos[tileset_uuid]['coordSystem2'] =\
            tileset_object.coordSystem2

    return JsonResponse(tileset_infos)


@api_view(['POST'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def link_tile(request):
    '''
    A file has been uploaded to S3. Finish the upload here by adding the file
    to the database.

    The request should contain the location that file was uploaded to.

    Parameters:
        request: The HTTP request associated with this POST action

    Returns:
        JsonResponse: A response containing the uuid of the newly added tileset
    '''
    body = json.loads(request.body.decode('utf8'))

    media_base_path = op.realpath(hss.MEDIA_ROOT)
    abs_filepath = op.realpath(op.join(media_base_path, body['filepath']))

    if abs_filepath.find(media_base_path) != 0:
        # check ot make sure that the filename is contained in the AWS_BUCKET_MOUNT
        # e.g. that somebody isn't surreptitiously trying to pass in ('../../file')
        return JsonResponse({'error': "Provided path ({}) not in the data path".format(body['filepath'])}, status=422)
    else:
        if not op.exists(abs_filepath):
            return JsonResponse({'error': "Specified file ({}) does not exist".format(body['filepath'])}, status=400)

    diff_path = abs_filepath[len(media_base_path)+1:]    # +1 for the slash

    tile_data = body.copy()
    tile_data.pop('filepath')
    # print("user:", request.user)
    try:
        obj = tm.Tileset.objects.create(
            datafile=diff_path,
            name=op.basename(body['filepath']),
            owner=request.user,
            **tile_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=422)


    return JsonResponse({'uuid': str(obj.uuid)}, status=201)

@api_view(['POST'])
@authentication_classes((CsrfExemptSessionAuthentication, BasicAuthentication))
def register_url(request):
    '''
    Register a url to use as a tileset and register it with the database.
    Parameters:
        request: The HTTP request associate with this post action
            url: the url of the file
            name: A name to give the tileset
            filetype: A filetype for the tileset
            datatype: A datatype for the tileset
            uid: A unique identifier for the tileset
            coordSystem:
            coordSystem2:
    Returns:
        HttpResponse code for the request, 200 if the action is successful
    '''
    body = json.loads(request.body.decode('utf8'))

    url = body.get('fileurl', None)
    media_base_path = op.realpath(hss.MEDIA_ROOT)
    logger.warn('URL to register %s' % url)

    # validate the url to ensure we didn't get garbage
    is_url = url != None #todo: replace with regex

    if not is_url:
        error = ({
            'error': 'Specified url ({}) is not valid.'.format(url)
        })
        return JsonResponse(error, 400)

    try:
        if not op.exists(media_base_path):
            os.makedirs(media_base_path)
        # ingest the file by calling the ingest_tileset command
        ingest_tileset_to_db(
            filename=url,
            datatype=body.get('datatype', None),
            filetype=body.get('filetype', None),
            coordSystem=body.get('coordSystem', ''),
            coordSystem2=body.get('coordSystem2', ''),
            project_name=body.get('project_name', ''),
            uid=body.get('uid', None),
            name=body.get('name', None),
            no_upload=True
        )
    except Exception as e:
        logger.error('Problem registering url: %s' % e)
        return JsonResponse(({
            'error': str(e)
        }), 500)

    return HttpResponse("Success", content_type="text/plain")


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
    parser_classes = (rfp.JSONParser, rfp.MultiPartParser,)

    def destroy(self, request, *args, **kwargs):
        '''Delete a tileset instance and underlying media upload
        '''
        uuid = self.kwargs['uuid']
        if not uuid:
            return JsonResponse({'error': 'uuid is undefined'}, status=400)
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            filename = instance.datafile.name
            filepath = op.join(hss.MEDIA_ROOT, filename)
            if not op.isfile(filepath):
                return JsonResponse({'error': 'Unable to locate tileset media file for deletion: {}'.format(filepath)}, status=500)
            os.remove(filepath)
        except dh.Http404:
            return JsonResponse({'error': 'Unable to locate tileset instance for uuid: {}'.format(uuid)}, status=404)
        except dbm.ProtectedError as dbpe:
            return JsonResponse({'error': 'Unable to delete tileset instance: {}'.format(str(dbpe))}, status=500)
        except OSError:
            return JsonResponse({'error': 'Unable to delete tileset media file: {}'.format(filepath)}, status=500)
        return HttpResponse(status=204)

    def retrieve(self, request, *args, **kwargs):
        '''Retrieve a serialized JSON object made from a subset of properties of a tileset instance
        '''
        uuid = self.kwargs['uuid']
        if not uuid:
            return JsonResponse({'error': 'The uuid parameter is undefined'}, status=400)
        try:
            queryset = tm.Tileset.objects.all().filter(uuid=uuid)
        except dce.ObjectDoesNotExist as dne:
            return JsonResponse({'error': 'Unable to retrieve tileset instance: {}'.format(str(dne))}, status=500)
        serializer = tss.UserFacingTilesetSerializer(queryset, many=True)
        try:
            instance = serializer.data[0]
        except IndexError as ie:
            return JsonResponse({'error': 'Unable to locate tileset instance for uuid: {}'.format(uuid)}, status=404)
        return JsonResponse(instance)

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
