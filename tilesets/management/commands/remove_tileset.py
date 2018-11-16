from django.core.management.base import BaseCommand, CommandError
import django.core.exceptions as dce
from django.core.files import File

import hgtiles.bigwig as hgbi
import slugid
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu
import os
import os.path as op
import tilesets.chromsizes  as tcs
from django.conf import settings


def remove(uid):
    if not uid:
        raise CommandError('uid must be specified')

    matches = tm.Tileset.objects.filter(uuid=uid)
    for match in matches:
        match.datafile.delete()
        match.delete()
    return len(matches)

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('uid', type=str)

    def handle(self, *args, **options):
        remove(options.get('uid', None))
