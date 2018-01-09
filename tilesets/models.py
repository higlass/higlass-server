from __future__ import unicode_literals

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
        return "Viewconf [uuid: " + self.uuid + ']'


class Tileset(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    uuid = models.CharField(max_length=100, unique=True, default=lambda: slugid.nice().decode('utf-8'))
    # processed_file = models.TextField()
    datafile = models.FileField(upload_to='uploads')
    filetype = models.TextField()
    datatype = models.TextField(default='unknown')

    coordSystem = models.TextField()
    coordSystem2 = models.TextField(default='')

    owner = models.ForeignKey(
        'auth.User', related_name='tilesets', on_delete=models.CASCADE,
        blank=True, null=True  # Allow anonymous owner
    )
    private = models.BooleanField(default=False)
    name = models.TextField(blank=True)

    class Meta:
        ordering = ('created',)
        permissions = (('view_tileset', "View tileset"),)

    def __str__(self):
        '''
        Get a string representation of this model. Hopefully useful for the
        admin interface.
        '''
        return "Tileset [name: " + self.name + '] [ft: ' + self.filetype + ']'
