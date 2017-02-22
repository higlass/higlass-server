from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('filename', nargs='+', type=str)


    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('TODO: ingest %s' % (options['filename'][0])))