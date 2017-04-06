from django.core.management.base import BaseCommand
from django.core.files import File
import slugid
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu
import os.path as op

class Command(BaseCommand):
    def add_arguments(self, parser):
        # TODO: filename, datatype, fileType and coordSystem should
        # be checked to make sure they have valid values
        # for now, coordSystem2 should take the value of coordSystem
        # if the datatype is matrix
        # otherwise, coordSystem2 should be empty
        parser.add_argument('--filename', type=str)
        parser.add_argument('--datatype', type=str)
        parser.add_argument('--filetype', type=str)
        parser.add_argument('--coordSystem', default='', type=str)
        parser.add_argument('--coordSystem2', default='', type=str)
        parser.add_argument('--uid', type=str)
        parser.add_argument('--name', type=str)

    def handle(self, *args, **options):
        filename = options['filename']
        datatype = options['datatype']
        filetype = options['filetype']
        coordSystem = options['coordSystem']
        coordSystem2 = options['coordSystem2']
        #coord = options['coord']
        uid = options.get('uid') or slugid.nice()

        name = options.get('name') or op.split(filename)[1]
        django_file = File(open(filename, 'r'))

        # remove the filepath of the filename
        django_file.name = op.split(django_file.name)[1]
        tm.Tileset.objects.create(
            datafile=django_file,
            filetype=filetype,
            datatype=datatype,
            coordSystem=coordSystem,
            coordSystem2=coordSystem2,
            owner=None,
            uuid=uid,
            name=name)
