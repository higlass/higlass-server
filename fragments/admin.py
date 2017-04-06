from django.contrib import admin

from guardian.admin import GuardedModelAdmin

from fragments.models import ChromInfo, ChromSizes


class ChromInfoAdmin(GuardedModelAdmin):
    list_display = [
        'created',
        'uuid',
        'datafile'
    ]


class ChromSizesAdmin(GuardedModelAdmin):
    list_display = [
        'created',
        'uuid',
        'datafile'
    ]


admin.site.register(ChromInfo, ChromInfoAdmin)
admin.site.register(ChromSizes, ChromSizesAdmin)
