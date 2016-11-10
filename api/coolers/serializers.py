from rest_framework import serializers
from coolers.models import Cooler, LANGUAGE_CHOICES, STYLE_CHOICES
from django.contrib.auth.models import User

class CoolerSerializer(serializers.HyperlinkedModelSerializer):
    #owner = serializers.ReadOnlyField(source='owner.username')
    generateTiles = serializers.HyperlinkedIdentityField(view_name='cooler-generatetiles', format='html')
    class Meta:
        model = Cooler
        fields = ('uuid', 'processed_file', 'file_type')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    	username = serializers.ReadOnlyField(source='username')
	coolers = serializers.HyperlinkedRelatedField(many=True, view_name='cooler-detail', read_only=True)

    	class Meta:
        	model = User
        	fields = ('url', 'id', 'username', 'coolers')

class UserSerializer(serializers.ModelSerializer):
    coolers = serializers.PrimaryKeyRelatedField(many=True, queryset=Cooler.objects.all())

    class Meta:
        model = User
        fields = ('id', 'username', 'coolers')

class CoolerSerializer(serializers.ModelSerializer):
     class Meta:
     #   owner = serializers.ReadOnlyField(source='owner.username')
        model = Cooler
        fields = ('uuid', 'processed_file', 'file_type')
