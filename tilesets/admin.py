from django.contrib import admin
from tilesets.models import Tileset
from tilesets.models import ViewConf
# Register your models here.


class TilesetAdmin(admin.ModelAdmin):
    list_display = [
        'created',
        'uuid',
        'datafile',
        'filetype',
        'datatype',
        'coordSystem',
        'coordSystem2',
        'owner',
        'private',
        'name',
    ]


class ViewConfAdmin(admin.ModelAdmin):
    list_display = [
        'created',
        'uuid',
        'higlassVersion',
    ]


admin.site.register(Tileset, TilesetAdmin)
admin.site.register(ViewConf, ViewConfAdmin)
