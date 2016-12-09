from __future__ import unicode_literals
from django.db import models
from rest_framework.decorators import api_view, permission_classes
from tilesets.permissions import IsOwnerOrReadOnly, IsRequestMethodGet
import uuid

class Tileset(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    #permission_classes = (IsRequestMethodGet,)
    uuid=models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    processed_file = models.TextField()
    file_type = models.TextField()
    owner = models.ForeignKey('auth.User', related_name='tilesets', on_delete=models.CASCADE)
    
    #language = models.CharField(choices=LANGUAGE_CHOICES, default='python', max_length=100)
    #style = models.CharField(choices=STYLE_CHOICES, default='friendly', max_length=100)
    class Meta:
        #model = Tileset
	#fields = ('uuid')
	ordering = ('created',)
# Create your models here.
