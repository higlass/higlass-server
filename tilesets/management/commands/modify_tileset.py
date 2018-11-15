from django.core.management.base import BaseCommand, CommandError
from django.db.models import ProtectedError
from django.conf import settings
import tilesets.models as tm
import os

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--uuid', type=str, required=True)
        parser.add_argument('--name', type=str)
        
    def handle(self, *args, **options):
        uuid = options.get('uuid')
        name = options.get('name')
        
        # search for Django object, modify associated record
        instance = tm.Tileset.objects.get(uuid=uuid)
        if not instance:
          raise CommandError('Instance for specified uuid [%s] was not found' % (uuid))
        else:
          try:
              instance_dirty = False
              
              # only change tileset name if specified, and if it is 
              # different from the current instance name
              if name and name != instance.name:
                  instance.name = name
                  instance_dirty = True
                  
              # if any changes were applied, persist them
              if instance_dirty:
                  instance.save()
          except ProtectedError:
              raise CommandError('Instance for specified uuid [%s] could not be modified' % (uuid))