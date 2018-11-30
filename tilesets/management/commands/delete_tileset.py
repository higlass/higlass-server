from django.core.management.base import BaseCommand, CommandError
from django.db.models import ProtectedError
from django.conf import settings
import tilesets.models as tm
import os

def delete(uuid):
    # search for Django object, remove associated file and record
    instance = tm.Tileset.objects.get(uuid=uuid)
    if not instance:
        raise CommandError('Instance for specified uuid ({}) was not found'.format(uuid))
    else:
        filename = instance.datafile.name
        filepath = os.path.join(settings.MEDIA_ROOT, filename)
        if not os.path.isfile(filepath):
            raise CommandError('File does not exist under media root')
        try:
            os.remove(filepath)
        except OSError:
            raise CommandError('File under media root could not be removed')
        try:
            instance.delete()
        except ProtectedError:
            raise CommandError('Instance for specified uuid ({}) could not be deleted'.format(uuid))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--uuid', type=str, required=True)

    def handle(self, *args, **options):
        delete(options.get(uuid))
