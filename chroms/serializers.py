from rest_framework import serializers
from chroms.models import Sizes

class ChromSizeObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sizes
        fields = ('uuid', 'coords')
