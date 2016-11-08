from __future__ import unicode_literals
from django.db import models
from pygments.lexers import get_all_lexers
from pygments.styles import get_all_styles
from pygments.lexers import get_lexer_by_name
from pygments.formatters.html import HtmlFormatter
from pygments import highlight
from rest_framework.decorators import api_view, permission_classes
from coolers.permissions import IsOwnerOrReadOnly, IsRequestMethodGet
import uuid

LEXERS = [item for item in get_all_lexers() if item[1]]
LANGUAGE_CHOICES = sorted([(item[1][0], item[0]) for item in LEXERS])
STYLE_CHOICES = sorted((item, item) for item in get_all_styles())


def save(self, *args, **kwargs):
    """
    Use the `pygments` library to create a highlighted HTML
    representation of the code snippet.
    """
    lexer = get_lexer_by_name(self.language)
    #linenos = self.linenos and 'table' or False
    options = self.title and {'title': self.title} or {}
    formatter = HtmlFormatter(style=self.style, linenos=linenos,
                              full=True, **options)
    self.highlighted = highlight(self.code, lexer, formatter)
    super(Cooler, self).save(*args, **kwargs)

class Cooler(models.Model):
    #created = models.DateTimeField(auto_now_add=True)
    #permission_classes = (IsRequestMethodGet,)
    uuid=models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    processed_file = models.TextField()
    twod = models.BooleanField(default=True)
    
    #language = models.CharField(choices=LANGUAGE_CHOICES, default='python', max_length=100)
    #style = models.CharField(choices=STYLE_CHOICES, default='friendly', max_length=100)
    #class Meta:
        #model = Cooler
	#fields = ('uuid')
	#ordering = ('created',)
# Create your models here.
