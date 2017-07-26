from django.contrib import admin
from annotations.models import Annotation, AnnotationSet, Locus, Pattern


class AnnotationAdmin(admin.ModelAdmin):
    list_display = [
        'slug',
        'created',
        'updated',
    ]


class AnnotationSetAdmin(admin.ModelAdmin):
    list_display = [
        'slug',
        'created',
        'updated',
    ]


class LocusAdmin(admin.ModelAdmin):
    list_display = [
        'chrom1',
        'start1',
        'end1',
        'chrom2',
        'start2',
        'end2',
        'coords',
        'created',
        'updated',
    ]


class PatternAdmin(admin.ModelAdmin):
    list_display = [
        'locus',
        'tileset',
        'zoom_out_level',
        'created',
        'updated',
    ]


admin.site.register(Annotation, AnnotationAdmin)
admin.site.register(AnnotationSet, AnnotationSetAdmin)
admin.site.register(Locus, LocusAdmin)
admin.site.register(Pattern, PatternAdmin)
