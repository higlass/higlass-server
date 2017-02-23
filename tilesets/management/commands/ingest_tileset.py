from django.core.management.base import BaseCommand
from django.contrib.auth.models import AnonymousUser
import slugid
import os
import guardian.utils as gu
import tilesets.serializers as tss
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu


class SizedFile(file):
    def __init__(self, *args, **kwargs):
        file.__init__(self, *args, **kwargs)
        self.size = os.path.getsize(self.name)
        self._committed = True

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--filename', type=str)
        parser.add_argument('--datatype', type=str)
        parser.add_argument('--filetype', type=str)
        #parser.add_argument('--coord', default='hg19', type=str)
        parser.add_argument('--uid', type=str)

    def handle(self, *args, **options):
        filename = options['filename']
        datatype = options['datatype']
        filetype = options['filetype']
        #coord = options['coord']
        uid = options.get('uid') or slugid.nice()

        upload_file = open(filename, 'r')
        datafile = dcfu.SimpleUploadedFile(upload_file.name, upload_file.read())
        tm.Tileset.objects.create(
            datafile=datafile,
            filetype=filetype,
            datatype=datatype,
            owner=None,
            uuid=uid)

        # data = {
        #     'datafile': SizedFile(filename),
        #     'datatype': datatype,
        #     'coordSystem': coord,
        #     #'coordSystem2': 'TODO',
        #     'filetype': filetype,
        #     'owner': AnonymousUser(),
        #     'private': False,
        #     'name': filename,
        #     'uuid': uid
        # }
        # serializer = tss.TilesetSerializer(data=data)
        # if serializer.is_valid():
        #     serializer.save()
        #     self.stdout.write('Ingested %s' % str(data))
        # else:
        #     self.stderr.write(str(serializer.errors))
