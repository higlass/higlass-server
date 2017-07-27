import uuid

from django.db import models
from tilsets.models import Tileset


class Locus(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    chrom1 = models.CharField(
        max_length=100, blank=False, null=False, default='chr1'
    )
    start1 = models.PositiveIntegerField(blank=False, null=False, default=0)
    end1 = models.PositiveIntegerField(blank=False, null=False, default=1)
    chrom2 = models.CharField(
        max_length=100, blank=True, null=True, default=None
    )
    start2 = models.PositiveIntegerField(blank=True, null=True, default=None)
    end2 = models.PositiveIntegerField(blank=True, null=True, default=None)

    coords = models.CharField(blank=False, null=False, default='hg19')

    class Meta:
        ordering = ('updated',)
        unique_together = (
            'chrom1', 'start1', 'end1', 'chrom2', 'start2', 'end2',
        )

    def __str__(self):
        return 'Locus [{} {} {} {} {} {}]'.format(
            self.chrom1,
            self.start1,
            self.end1,
            self.chrom2 if self.chrom2 else '-',
            self.start2 if self.start2 else '-',
            self.end2 if self.end2 else '-',
        )

    def is_2d(self, x):
        return (
            self.chrom2 is not None and
            self.start2 is not None and
            self.end2 is not None
        )


class Pattern(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    locus = models.ForeignKey(Locus, on_delete=models.CASCADE)
    tileset = models.ForeignKey(Tileset, on_delete=models.CASCADE)

    """
    Since we can only coarsify raw data the zoom out level makes most sense to
    me as it has a natural start while the zoom (in) level does not.
    """
    zoom_out_level = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('updated',)
        unique_together = ('locus', 'tileset', 'zoom_out_level')

    def __str__(self):
        return "Pattern [uuid: " + self.uuid + ']'


class Annotation(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    slug = models.SlugField(max_length=100, blank=True, null=True, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    description = models.TextField()
    patterns = models.ManyToManyField(Pattern)

    class Meta:
        ordering = ('updated',)

    def __str__(self):
        return 'AnnotationSet [slug: {}]'.format(self.slug)

    def length(self):
        return self.patterns.count()


class AnnotationSet(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    slug = models.SlugField(max_length=100, blank=True, null=True, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    description = models.TextField()
    annotations = models.ManyToManyField(Annotation)

    class Meta:
        ordering = ('updated',)

    def __str__(self):
        return 'AnnotationSet [slug: {}]'.format(self.slug)

    def length(self):
        return self.annotations.count()
