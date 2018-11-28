import logging

from rest_framework import serializers
from tilesets.models import Tileset, ViewConf
from django.contrib.auth.models import User
import tilesets.generate_tiles as tgt
import tilesets.models as tm
import rest_framework.utils as rfu
from django.core.files.base import File

logger = logging.getLogger(__name__)

def get_or_create_tag(tag):
    tag_obj = tm.Tag.objects.filter(name=tag['name'])
    if tag_obj.count() == 0:
        # this tag doesn't exist so we need to create it
        ts = TagSerializer(data=tag)
        if not ts.is_valid():
            # something is wrong with this tag so we'll ignore it
            return None
        ts.save()
        tag_obj = tm.Tag.objects.get(name=tag['name'])
        tag_obj.refs = 1
        tag_obj.save()
    else:
        tag_obj = tm.Tag.objects.get(name=tag['name'])
        tag_obj.refs += 1
        tag_obj.save()
    return tag_obj

class ProjectsSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = tm.Project
        fields = (
                'uuid',
                'name',
                'description',
                'private'
            )

class UserSerializer(serializers.ModelSerializer):
    tilesets = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tileset.objects.all()
    )

    class Meta:
        model = User
        fields = ('id', 'username')


class ViewConfSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewConf
        fields = ('uuid', 'viewconf')

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = tm.Tag
        fields = (
            'name',
            'description',
            'refs'
        )

class TilesetTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = tm.Tag
        fields = (
            'name',
            'description',
        )
        extra_kwargs = {
                'name': { 'validators': []},
            }

class TilesetSerializer(serializers.ModelSerializer):
    tags = TilesetTagSerializer(many=True)
    project = serializers.SlugRelatedField(
            queryset=tm.Project.objects.all(),
            slug_field='uuid',
            allow_null=True,
            required=False)
    # datatype = serializers.SerializerMethodField('tags_to_datatype')

    def update(self, instance, validated_data):
        tag_data = []

        if 'tags' in validated_data:
            tag_data = validated_data.pop('tags')

        # add missing tags
        for tag in tag_data:
            if 'name' not in tag or len(tag['name']) == 0:
                # if the tag has no name, then we can't save it
                continue

            tag_obj = get_or_create_tag(tag)
            if tag_obj is None:
                continue

            instance.tags.add(tag_obj.pk)
            instance.save()

        # remove tags that are in the instance but not in the passed
        # data
        tag_names = set([tag['name'] for tag in tag_data])
        for tag in instance.tags.all():
            if tag.name not in tag_names:
                instance.tags.remove(tag)
                tag.refs -= 1;
                tag.save()
        #for tag_pair in instance.tags:

        # save all the other fields
        # Code copied from:
        # https://github.com/encode/django-rest-framework/blob/master/rest_framework/serializers.py
        # Simply set each attribute on the instance, and then save it.
        # Note that unlike `.create()` we don't need to treat many-to-many
        # relationships as being a special case. During updates we already
        # have an instance pk for the relationships to be associated with.
        info = rfu.model_meta.get_field_info(instance)

        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                field = getattr(instance, attr)
                field.set(value)
            else:
                setattr(instance, attr, value)

        instance.save()

        return instance

    def create(self, validated_data):
        # Taken from this StackOverflow question:
        # https://stackoverflow.com/questions/28706072/drf-3-creating-many-to-many-update-create-serializer-with-though-table
        # remove the tags otherwise the serializer will complain
        tag_data = validated_data.pop('tags')
        new_obj = tm.Tileset.objects.create(**validated_data)
        validated_data['tags'] = tag_data

        attrs_to_delete = []

        # don't try to update files because they've already been
        # saved
        for attr in validated_data:
            if isinstance(getattr(new_obj, attr), File):
                attrs_to_delete += [attr]


        for attr in attrs_to_delete:
            validated_data.pop(attr)
            # print(isinstance(getattr(new_obj, attr), File))

        new_obj = self.update(new_obj, validated_data)
        return new_obj

    class Meta:
        owner = serializers.ReadOnlyField(source='owner.username')
        model = tm.Tileset
        fields = (
            'uuid',
            'datafile',
            'filetype',
            'datatype',
            'name',
            'coordSystem',
            'coordSystem2',
            'created',
            'tags',
            'project',
            'description',
            'private',
        )

    def tags_to_datatype(self, obj):
        return tgt.get_tileset_datatype(obj)


class UserFacingTilesetSerializer(TilesetSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    tags = TagSerializer(many=True)
    # datatype = serializers.SerializerMethodField('tags_to_datatype')
    project_name = serializers.SerializerMethodField('retrieve_project_name')
    project_owner = serializers.SerializerMethodField('retrieve_project_owner')

    def tags_to_datatype(self, obj):
        return tgt.get_tileset_datatype(obj)

    def retrieve_project_name(self, obj):
        if obj.project is None:
            return ''

        return obj.project.name

    def retrieve_project_owner(self, obj):
        if obj.project is None:
            return ''

        return obj.project.owner.username

    class Meta:
        model = tm.Tileset
        fields = (
            'uuid',
            'filetype',
            'datatype',
            'private',
            'name',
            'coordSystem',
            'coordSystem2',
            'created',
            'owner',
            'tags',
            'project_name',
            'project_owner',
            'description',
        )
