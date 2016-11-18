from rest_framework import serializers
from tilesets.models import Tileset, LANGUAGE_CHOICES, STYLE_CHOICES
from django.contrib.auth.models import User

class TilesetSerializer(serializers.HyperlinkedModelSerializer):
    #owner = serializers.ReadOnlyField(source='owner.username')
    generateTiles = serializers.HyperlinkedIdentityField(view_name='tileset-generatetiles', format='html')
    class Meta:
        model = Tileset
        fields = ('uuid', 'processed_file', 'file_type')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    	username = serializers.ReadOnlyField(source='username')
	tilesets = serializers.HyperlinkedRelatedField(many=True, view_name='tileset-detail', read_only=True)

    	class Meta:
        	model = User
        	fields = ('url', 'id', 'username', 'tilesets')

class UserSerializer(serializers.ModelSerializer):
    tilesets = serializers.PrimaryKeyRelatedField(many=True, queryset=Tileset.objects.all())

    class Meta:
        model = User
        fields = ('id', 'username', 'tilesets')

class TilesetSerializer(serializers.ModelSerializer):
     class Meta:
     #   owner = serializers.ReadOnlyField(source='owner.username')
        model = Tileset
        fields = ('uuid', 'processed_file', 'file_type')
