from __future__ import unicode_literals

import slugid

from django.db import models


class Sizes(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    uuid = models.CharField(max_length=100, unique=True, default=slugid.nice)
    datafile = models.TextField()

    class Meta:
        ordering = ('created',)
