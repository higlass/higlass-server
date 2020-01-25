import logging

from rest_framework import serializers
from tilesets.models import Tileset, ViewConf
from django.contrib.auth.models import User
import tilesets.generate_tiles as tgt
import tilesets.models as tm
import rest_framework.utils as rfu
from django.core.files.base import File

logger = logging.getLogger(__name__)


class ProjectsSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = tm.Project
        fields = ("uuid", "name", "description", "private")


class UserSerializer(serializers.ModelSerializer):
    tilesets = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tileset.objects.all()
    )

    class Meta:
        model = User
        fields = ("id", "username")


class ViewConfSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewConf
        fields = ("uuid", "viewconf")


class TilesetSerializer(serializers.ModelSerializer):
    project = serializers.SlugRelatedField(
        queryset=tm.Project.objects.all(),
        slug_field="uuid",
        allow_null=True,
        required=False,
    )
    project_name = serializers.SerializerMethodField("retrieve_project_name")

    def retrieve_project_name(self, obj):
        if obj.project is None:
            return ""

        return obj.project.name

    class Meta:
        owner = serializers.ReadOnlyField(source="owner.username")
        model = tm.Tileset
        fields = (
            "uuid",
            "datafile",
            "filetype",
            "datatype",
            "name",
            "coordSystem",
            "coordSystem2",
            "created",
            "project",
            "project_name",
            "description",
            "private",
        )


class UserFacingTilesetSerializer(TilesetSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")
    project_name = serializers.SerializerMethodField("retrieve_project_name")
    project_owner = serializers.SerializerMethodField("retrieve_project_owner")

    def retrieve_project_name(self, obj):
        if obj.project is None:
            return ""

        return obj.project.name

    def retrieve_project_owner(self, obj):
        if obj.project is None:
            return ""

        if obj.project.owner is None:
            return ""

        return obj.project.owner.username

    class Meta:
        model = tm.Tileset
        fields = (
            "uuid",
            "filetype",
            "datatype",
            "private",
            "name",
            "coordSystem",
            "coordSystem2",
            "created",
            "owner",
            "project_name",
            "project_owner",
            "description",
        )
