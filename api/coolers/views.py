from coolers.models import Cooler
from coolers.serializers import CoolerSerializer
from coolers.serializers import UserSerializer
from rest_framework import generics
from django.contrib.auth.models import User
from rest_framework import permissions
from coolers.permissions import IsOwnerOrReadOnly
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework import renderers
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.decorators import api_view, permission_classes
from coolers.permissions import IsOwnerOrReadOnly
from django.views.decorators.gzip import gzip_page
import os
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
import numpy
import higlass_getter as hgg
from tiles import makeTile
from itertools import chain
from django.db.models import Q

def makeUnaryDict(hargs,queryset):
	odict = {}
	odict["_index"] = "hg19.1"
	odict["_type"] = "notimportant"
	odict["_id"] = hargs
	odict["_version"] = 1
	odict["_source"] = {}
	odict["_source"]["tile_value"] = {}
	odict["_source"]["tile_id"] = hargs
	prea = hargs.split('.')
	prea[0] = prea[0][1:]
	numerics = prea[1:4]
	nuuid = prea[0]
	argsa = map(lambda x:int(x), numerics)
	cooler = queryset.filter(uuid=nuuid).first()
	odict["_source"]["tile_value"]["dense"] = map(lambda x: float("{0:.1f}".format(x)),makeTile(argsa[0],argsa[1],argsa[2],cooler.processed_file))
	odict["_source"]["tile_value"]["min_value"] = min(odict["_source"]["tile_value"]["dense"])
	odict["_source"]["tile_value"]["max_value"] = max(odict["_source"]["tile_value"]["dense"])
	return odict
	

@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'users': reverse('user-list', request=request, format=format),
        'coolers': reverse('cooler-list', request=request, format=format)
    })


#@method_decorator(gzip_page, name='dispatch')
#class TilesViewSet(viewsets.ModelViewSet):
#	queryset = Cooler.objects.all()	
#	serializer_class = CoolerSerializer
	

#return JsonResponse(odict,safe=False) 


@method_decorator(gzip_page, name='dispatch')
class CoolersViewSet(viewsets.ModelViewSet):
    """
    Coolers
    """
    def get_queryset(self):
        queryset = super(CoolersViewSet, self).get_queryset()
	
	return queryset
	
    queryset = Cooler.objects.all()
    serializer_class = CoolerSerializer
    #permission_classes = (IsOwnerOrReadOnly,)	
    lookup_field='uuid'

    @detail_route(renderer_classes=[renderers.StaticHTMLRenderer])
    def render(self, request, *arg, **kwargs):
                queryset=Cooler.objects.all()
		hargs = request.GET.getlist("d")
                arr = []
                for elems in hargs:
                        arr.append(makeUnaryDict(elems,queryset))
                return JsonResponse(arr,safe=False)

    @detail_route(renderer_classes=[renderers.StaticHTMLRenderer])    
    def tileset_info(self, request, *args, **kwargs):
	cooler = self.get_object()
	info = hgg.getInfo(cooler.processed_file)
	od = {}
	od["_source"] = {}
	od["_source"]["tile_value"] = info
	od["_source"]["tile_id"] = "tileset_info"
	return JsonResponse(od, safe=False)


    
    @detail_route(renderer_classes=[renderers.StaticHTMLRenderer])
    def generate_tiles(self, request, *args, **kwargs):
        cooler = self.get_object()
	serializer = CoolerSerializer(cooler,data=request.data)
        cooler.rawfile_in_db = True
	idv = cooler.id
	#os.system("source activate snakes")
	os.system("wget "+cooler.url)	
        urlval = cooler.url.split('/')[-1]
	os.system("mv "+str(urlval)+" "+str(urlval).lower())
	urlval = urlval.lower()
	os.system("python recursive_agg_onefile.py"+urlval)
	cooler.processed_file = '.'.join(urlval.split('.')[:-1])+".multires.cool"
	cooler.processed = True
	cooler.save()
	return HttpResponseRedirect("/coolers/")

    def perform_create(self, serializer):
        serializer.save()
	return HttpResponse("test")

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Users
    """
    def get_queryset(self):
        queryset = super(UserViewSet, self).get_queryset()

        if self.request.user.is_staff:
                queryset = queryset
	elif self.request.user.is_authenticated():
                queryset = queryset.filter(username=self.request.user)
	else:
	    queryset = User.objects.none()

        return queryset
    permission_classes = (IsOwnerOrReadOnly,)
    queryset = User.objects.all()
    serializer_class = UserSerializer
