from django.core.management.base import BaseCommand
import slugid
import rest_framework.exceptions as rfe
import os.path as op
import guardian.utils as gu
import tilesets.serializers as tss

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('filename', type=str)


    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('TODO: ingest %s' % (options['filename'][0])))

        data = {
            'owner': gu.get_anonymous_user(),
            'private': False,
            'name': options['filename'][0],
            'uuid': slugid.nice()
        }
        serializer = tss.TilesetSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
        else:
            raise ValueError