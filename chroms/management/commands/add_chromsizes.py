from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
import django.core.files.uploadedfile as dcfu
import os.path as op
import slugid
from django.conf import settings
from chroms.models import Sizes
from chroms.utils import is_subdir


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            type=str,
            help='Path to the CSV file',
        )

        parser.add_argument(
            'coords',
            type=str,
            help='Coordinate system. E.g., hg19 or mm9',
        )

        parser.add_argument(
            '-i'
            '--id',
            dest='id',
            type=str,
            help='Identifier. If not given a random UUID is assigned',
        )

        parser.add_argument(
            '-n',
            '--no-upload',
            action='store_true',
            dest='no_upload',
            default=False,
            help='Skip upload. Only works when the file is already located ' +
            'in the media directory',
        )

    def handle(self, *args, **options):
        if options['no_upload']:
            file_abs_path = op.abspath(options['file'])

            if not is_subdir(op.dirname(file_abs_path), settings.MEDIA_ROOT):
                raise CommandError('File is not under media root')

            if not op.isfile(options['file']):
                raise CommandError(
                    'File (%s) does not exist under media (%s)' % (
                        op.dirname(file_abs_path),
                        settings.MEDIA_ROOT
                    )
                )

            django_file = op.relpath(options['file'], settings.MEDIA_ROOT)
        else:
            django_file = File(open(options['file'], 'r'))

            # remove the filepath of the filename
            django_file.name = op.split(django_file.name)[1]
            django_file = dcfu.SimpleUploadedFile(
                django_file.name, django_file.read()
            )

        print type(options['id'])

        if not options['coords']:
            raise CommandError('You need to specify a coordinate system')

        uuid = options['id'] or slugid.nice()

        try:
            Sizes.objects.get(uuid=uuid)
            raise CommandError('ID already exist')
        except Sizes.DoesNotExist:
            pass

        Sizes.objects.create(
            datafile=django_file,
            uuid=uuid,
            coords=options['coords'],
        )

        print 'Added chrom-sizes with ID: %s' % uuid
