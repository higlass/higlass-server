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
    return slugid.nice().decode('utf-8')

class Tag(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    # uuid not necessary since name is unique
    #uuid = models.CharField(max_length=100, unique=True, default=lambda: slugid.nice().decode('utf-8'))
    name = models.TextField(unique=True)
    description = models.TextField(default='', blank=True)
    refs = models.IntegerField(default=0)

    def __str__(self):
        return "Tag [value: " + self.name + "]"

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
    filetype = models.TextField()
    datatype = models.TextField(default='unknown')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, 
            blank=True, null=True)
    tags = models.ManyToManyField(Tag, blank=True)
    description = models.TextField(blank=True)

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
