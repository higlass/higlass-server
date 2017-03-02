from django.core.management.base import BaseCommand
import slugid
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu
import os.path as op

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--filename', type=str)
        parser.add_argument('--datatype', type=str)
        parser.add_argument('--filetype', type=str)
        #parser.add_argument('--coord', default='hg19', type=str)
        parser.add_argument('--uid', type=str)
        parser.add_argument('--name', type=str)

    def handle(self, *args, **options):
        filename = options['filename']
        datatype = options['datatype']
        filetype = options['filetype']
        #coord = options['coord']
        uid = options.get('uid') or slugid.nice()
        name = options.get('name') or op.split(filename)[1]

        upload_file = open(filename, 'r')
        datafile = dcfu.SimpleUploadedFile(upload_file.name, upload_file.read())
        tm.Tileset.objects.create(
            datafile=datafile,
            filetype=filetype,
            datatype=datatype,
            owner=None,
            uuid=uid,
            name=name)
