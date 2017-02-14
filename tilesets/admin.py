from django.contrib import admin
from tilesets.models import Tileset
from tilesets.models import ViewConf
# Register your models here.

class TilesetAdmin(admin.ModelAdmin):
    pass

class ViewConfAdmin(admin.ModelAdmin):
    pass

admin.site.register(Tileset, TilesetAdmin)
admin.site.register(ViewConf, ViewConfAdmin)