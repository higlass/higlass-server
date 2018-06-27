from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
import slugid
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu
import os.path as op
from django.conf import settings


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        for tileset in tm.Tileset.objects.all():
            print('tileset:', tileset)
