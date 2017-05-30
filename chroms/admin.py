from django.contrib import admin

from guardian.admin import GuardedModelAdmin

from chroms.models import Sizes


class SizesAdmin(GuardedModelAdmin):
    list_display = [
        'created',
        'coords',
        'uuid',
        'datafile'
    ]


admin.site.register(Sizes, SizesAdmin)
