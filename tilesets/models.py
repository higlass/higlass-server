from __future__ import unicode_literals

import django
import django.contrib.auth.models as dcam
import slugid

from django.db import models


class ViewConf(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    higlassVersion = models.CharField(max_length=16, default='')
    uuid = models.CharField(max_length=100, unique=True, default=slugid.nice)
    viewconf = models.TextField()

    class Meta:
        ordering = ('created',)

    def __str__(self):
        '''
        Get a string representation of this model. Hopefully useful for the
        admin interface.
        '''
        return "Viewconf [uuid: {}]".format(self.uuid)

def decoded_slugid():
    return slugid.nice()

class Project(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    last_viewed_time = models.DateTimeField(default=django.utils.timezone.now)

    owner = models.ForeignKey(dcam.User, on_delete=models.CASCADE, blank=True, null=True)
    name = models.TextField(unique=True)
    description = models.TextField(blank=True)
    uuid = models.CharField(max_length=100, unique=True, default=decoded_slugid)
    private = models.BooleanField(default=False)

    class Meta:
        ordering = ('created',)
        permissions = (('read', "Read permission"),
                ('write', 'Modify tileset'),
                ('admin', 'Administrator priviliges'),
            )

    def __str__(self):
        return "Project [name: " + self.name + "]"

class Tileset(models.Model):
    created = models.DateTimeField(auto_now_add=True)

    uuid = models.CharField(max_length=100, unique=True, default=decoded_slugid)

    # processed_file = models.TextField()
    datafile = models.FileField(upload_to='uploads')

    # indexfile is used for bam files
    indexfile = models.FileField(upload_to='uploads', default=None, null=True)
    filetype = models.TextField()
    datatype = models.TextField(default='unknown', blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
            blank=True, null=True)
    description = models.TextField(blank=True)

    coordSystem = models.TextField()
    coordSystem2 = models.TextField(default='', blank=True)
    temporary = models.BooleanField(default=False)

    owner = models.ForeignKey(
        'auth.User', related_name='tilesets', on_delete=models.CASCADE,
        blank=True, null=True  # Allow anonymous owner
    )
    private = models.BooleanField(default=False)
    name = models.TextField(blank=True)

    class Meta:
        ordering = ('created',)
        permissions = (('read', "Read permission"),
                ('write', 'Modify tileset'),
                ('admin', 'Administrator priviliges'),
            )

    def __str__(self):
        '''
        Get a string representation of this model. Hopefully useful for the
        admin interface.
        '''
        return "Tileset [name: {}] [ft: {}] [uuid: {}]".format(self.name, self.filetype, self.uuid)
