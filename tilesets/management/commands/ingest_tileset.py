from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
import slugid
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu
import os.path as op
from django.conf import settings


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
        # parser.add_argument('--coord', default='hg19', type=str)
        parser.add_argument('--uid', type=str)
        parser.add_argument('--name', type=str)

        # Named (optional) arguments
        parser.add_argument(
            '--no-upload',
            action='store_true',
            dest='no_upload',
            default=False,
            help='Skip upload',
        )

    def handle(self, *args, **options):
        filename = options['filename']
        datatype = options['datatype']
        filetype = options['filetype']
        coordSystem = options['coordSystem']
        coordSystem2 = options['coordSystem2']
        # coord = options['coord']
        uid = options.get('uid') or slugid.nice().decode('utf-8')
        name = options.get('name') or op.split(filename)[1]

        if options['no_upload']:
            if not op.isfile(op.join(settings.MEDIA_ROOT, filename)):
                raise CommandError('File does not exist under media root')
            django_file = filename
        else:
            django_file = File(open(filename, 'rb'))

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
