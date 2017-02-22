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
        # ('uuid', 'datafile', 'filetype', 'datatype', 'private', 'name', 'coordSystem', 'coordSystem2')
        filename = options['filename']

        data = {
            'datafile': open(filename),
            'datatype': 'TODO',
            'coordSystem': 'TODO',
            'coordSystem2': 'TODO',
            'filetype': 'TODO',

            'owner': gu.get_anonymous_user(),
            'private': False,
            'name': filename,
            'uuid': slugid.nice()
        }
        serializer = tss.TilesetSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            self.stderr.write(self.style.SUCCESS('Ingested %s' % str(data)))
        else:
            self.stderr.write(self.style.ERROR(str(serializer.errors)))
