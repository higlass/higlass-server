from django.core.management.base import BaseCommand
import slugid
import os
import guardian.utils as gu
import tilesets.serializers as tss


class SizedFile(file):
    def __init__(self, *args, **kwargs):
        file.__init__(self, *args, **kwargs)
        self.size = os.path.getsize(self.name)
        self._committed = True

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('filename', type=str)

    def handle(self, *args, **options):
        filename = options['filename']

        self.stderr.write('filename: %s' % filename)
        data = {
            'datafile': SizedFile(filename),
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
            self.stderr.write('Ingested %s' % str(data))
        else:
            self.stderr.write(str(serializer.errors))