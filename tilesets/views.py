from tilesets.models import Tileset
from tilesets.serializers import TilesetSerializer
from tilesets.serializers import UserSerializer
from rest_framework import generics
from django.contrib.auth.models import User
from rest_framework import permissions
from tilesets.permissions import IsOwnerOrReadOnly
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.decorators import api_view, permission_classes
from tilesets.permissions import IsOwnerOrReadOnly
from django.views.decorators.gzip import gzip_page
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from tiles import makeTile

import base64
import clodius.hdf_tiles as hdft
import cooler
import django.db.models as dbm
import getter
import guardian.compat as gc
import guardian.utils as gu
import h5py
import json
import math
import multiprocessing as mp
import numpy as np
import os
import os.path as op
import rest_framework.exceptions as rfe
import slugid
import urllib

global mats
mats = {}


def makeMats(dset):
    f = h5py.File(dset, 'r')
    mats[dset] = [f, getter.get_info(dset)]


def make_cooler_tile(cooler_filepath, tile_position):
    '''Create a tile from a cooler file.

    Args:
        cooler_filepath (str): The location of the cooler file that we'll
            that we'll extract the tile data from.
        tile_position (list): The position of the tile ([z,x,y])

    Returns:
        dict: The tile data consisting of a 'dense' member containing
            the data array as well as 'min_value' and 'max_value' which
            contain the minimum and maximum values in the 'dense' array.
    '''
    tile_data = {}

    if mats.has_key(cooler_filepath) == False:
        makeMats(cooler_filepath)

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

    tile = makeTile(tile_position[0], tile_position[1], tile_position[2],
                                  mats[cooler_filepath])
    tile_data["min_value"] = float(np.min(tile))
    tile_data["max_value"] = float(np.max(tile))
    tile_data['dense'] = base64.b64encode(tile)

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
    #queryset = Tileset.objects.all()
    tile_id_parts = tile_id.split('.')
    tile_position = map(int, tile_id_parts[1:])
    tileset_uuid = tile_id_parts[0]

    tileset = Tileset.objects.get(uuid=tileset_uuid)

    if tileset.private and request.user != tileset.owner:
        # dataset is not public return an empty set
        return (tileset_uuid, {'error': "Forbidden"})

    if tileset.file_type == "hitile":
        dense = hdft.get_data(h5py.File(tileset.processed_file),
                    tile_position[0],
                    tile_position[1])

        return (tile_id,
                {'dense': base64.b64encode(dense)})

    elif tileset.file_type == "elasticsearch":
        response = urllib.urlopen(
            tileset.processed_file + '/' + '.'.join(map(str,tile_position)))
        return (tile_id, json.loads(response.read())["_source"]["tile_value"])
    else:
        tile_data = make_cooler_tile(tileset.processed_file, tile_position)
        if tile_data is None:
            return None
        return (tile_id, tile_data)
        # od[ud[1]] = ud[0]

class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

@api_view(['GET'])
def tiles(request):
    global mats

    # create a set so that we don't fetch the same tile multiple times
    tileids_to_fetch = set(request.GET.getlist("d"))
    # with ProcessPoolExecutor() as executor:
    #	res = executor.map(parallelize, hargs)
    '''
    p = mp.Pool(4)
    res = p.map(parallelize, hargs)
    '''

    res = map(lambda x: generate_tile(x, request), tileids_to_fetch)

    # create a dictionary of tileids
    result_dict = dict([i for i in res if i is not None])

    return JsonResponse(result_dict, safe=False)

@api_view(['GET'])
def tileset_info(request):
    global mats
    queryset = Tileset.objects.all()
    hargs = request.GET.getlist("d")
    d = {}
    for elems in hargs:
        cooler = queryset.filter(uuid=elems).first()

        if cooler.private and request.user != cooler.owner:
            # dataset is not public
            d[elems] = {'error': "Forbidden"}
            continue

        if cooler.file_type == "hitile":
            tileset_info = hdft.get_tileset_info(
                h5py.File(cooler.processed_file))
            d[elems] =  {
                    "min_pos": [0],
                    "max_pos": [tileset_info['max_pos']],
                    "max_width": 2 ** math.ceil(math.log(tileset_info['max_pos'] - 0) / math.log(2)),
                    "tile_size": tileset_info['tile_size'],
                    "max_zoom": tileset_info['max_zoom']
                }
        elif cooler.file_type == "elastic_search":
            response = urllib.urlopen(
                cooler.processed_file + "/tileset_info")
            d[elems] = json.loads(response.read())
        else:
            dsetname = queryset.filter(uuid=elems).first().processed_file
            if mats.has_key(dsetname) == False:
                makeMats(dsetname)
            d[elems] = mats[dsetname][1]
    return JsonResponse(d, safe=False)

@method_decorator(gzip_page, name='dispatch')
class TilesetsViewSet(viewsets.ModelViewSet):
    """
    Tilesets
    """

    def get_queryset(self):

        # debug NOT SECURE
        queryset = super(TilesetsViewSet, self).get_queryset()
        return queryset

        # secure production
        return Tileset.objects.none()

    queryset = Tileset.objects.all()
    serializer_class = TilesetSerializer
    # permission_classes = (IsOwnerOrReadOnly,)
    lookup_field = 'uuid'

    def list(self, request, *args, **kwargs):
        # only return tilesets which are accessible by this user
        if request.user.is_anonymous:
            user = gu.get_anonymous_user()
        else:
            user = request.user

        queryset = self.queryset.filter(dbm.Q(owner=user) | dbm.Q(private=False))

        if 'ac' in request.GET:
            queryset = queryset.filter(name__contains=request.GET['ac'])
        if 't' in request.GET:
            queryset = queryset.filter(file_type__contains=request.GET['t'])

        ts_serializer = TilesetSerializer(queryset, many=True)
        return JsonResponse({"count": len(queryset), "results": ts_serializer.data})
        #return self.list(request, *args, **kwargs)

    def perform_create(self, serializer):
        anonymous_user = gc.get_user_model().get_anonymous()

        if 'uid' in self.request.data:
            try:
                self.queryset.get(uuid = self.request.data['uid'])
                # this uid already exists, return an error
                raise rfe.APIException("UID already exists")
            except Tileset.DoesNotExist:
                uid = self.request.data['uid']
        else:
            uid = slugid.nice()


        if 'name' in self.request.data:
            name = self.request.data['name']
        else:
            name = op.split(self.request.data['processed_file'])[1]

        if self.request.user.is_anonymous:
            # can't create a private dataset as an anonymous user
            serializer.save(owner=gu.get_anonymous_user(), private=False, name=name, uuid=uid)
        else:
            serializer.save(owner=self.request.user, name=name, uuid=uid)

        return HttpResponse("test")
