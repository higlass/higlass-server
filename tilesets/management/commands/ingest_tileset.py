from django.core.management.base import BaseCommand, CommandError
import django.core.exceptions as dce
from django.core.files import File

import clodius.tiles.bigwig as hgbi
import slugid
import tilesets.models as tm
import django.core.files.uploadedfile as dcfu
import logging
import os
import os.path as op
import tilesets.chromsizes  as tcs
from django.conf import settings

logger = logging.getLogger(__name__)

def remote_to_local(filename, no_upload):
    if filename[:7] == 'http://':
        filename = "{}..".format(filename.replace('http:/', 'http'))
        no_upload=True
    if filename[:8] == 'https://':
        filename = "{}..".format(filename.replace('https:/', 'https'))
        no_upload=True
    if filename[:6] == 'ftp://':
        filename = "{}..".format(filename.replace('ftp:/', 'ftp'))
        no_upload=True

    return (filename, no_upload)

def ingest(filename=None, datatype=None, filetype=None, coordSystem='', coordSystem2='',
        uid=None, name=None, no_upload=False, project_name='',
        indexfile=None, temporary=False, **ignored):
    uid = uid or slugid.nice()
    name = name or op.split(filename)[1]

    if not filetype:
        raise CommandError('Filetype has to be specified')

    django_file = None
    index_file = None

    # bamfiles need to be ingested with an index, if it's not
    # specified as a parameter, try to find it at filename + ".bai"
    # and complain if it can't be found
    if filetype == 'bam':
        if indexfile is None:
            indexfile = filename + '.bai'
            if not op.exists(indexfile):
                print(f'Index for bamfile {indexfile} not found. '+
                    'Either specify explicitly using the --indexfile parameter ' +
                    'or create it in the expected location.')
                return

    # if we're ingesting a url, place it relative to the httpfs directories
    # and append two dots at the end

    filename, no_upload = remote_to_local(filename, no_upload)
    if indexfile:
        (indexfile, _) = remote_to_local(indexfile, no_upload)

    # it's a regular file on the filesystem, not a file being entered as a url
    if no_upload:
        if (not op.isfile(op.join(settings.MEDIA_ROOT, filename)) and
            not op.islink(op.join(settings.MEDIA_ROOT, filename)) and
            not any([filename.startswith('http/'), filename.startswith('https/'), filename.startswith('ftp/')])):
            raise CommandError('File does not exist under media root')
        filename = op.join(settings.MEDIA_ROOT, filename)
        django_file = filename
        if indexfile:
            if (not op.isfile(op.join(settings.MEDIA_ROOT, indexfile)) and
                not op.islink(op.join(settings.MEDIA_ROOT, indexfile)) and
                not any([indexfile.startswith('http/'), indexfile.startswith('https/'), indexfile.startswith('ftp/')])):
                raise CommandError('Index file does not exist under media root')
            indexfile = op.join(settings.MEDIA_ROOT, indexfile)
            index_file = indexfile
    else:
        if os.path.islink(filename):
            django_file = File(open(os.readlink(filename),'rb'))
            if indexfile:
                index_file = File(open(os.readlink(indexfile, 'rb')))
        else:
            django_file = File(open(filename,'rb'))
            if indexfile:
                index_file = File(open(indexfile, 'rb'))

        # remove the filepath of the filename
        django_file.name = op.split(django_file.name)[1]
        if index_file:
            index_file.name = op.split(index_file.name)[1]

    if filetype.lower() == 'bigwig':
        coordSystem = check_for_chromsizes(filename, coordSystem)

    try:
        project_obj = tm.Project.objects.get(name=project_name)
    except dce.ObjectDoesNotExist:
        project_obj = tm.Project.objects.create(
            name=project_name
        )

    return tm.Tileset.objects.create(
        datafile=django_file,
        indexfile=index_file,
        filetype=filetype,
        datatype=datatype,
        coordSystem=coordSystem,
        coordSystem2=coordSystem2,
        owner=None,
        project=project_obj,
        uuid=uid,
        temporary=temporary,
        name=name)

def chromsizes_match(chromsizes1, chromsizes2):
    pass

def check_for_chromsizes(filename, coord_system):
    '''
    Check to see if we have chromsizes matching the coord system
    of the filename.

    Parameters
    ----------
    filename: string
        The name of the bigwig file
    coord_system: string
        The coordinate system (assembly) of this bigwig file
    '''
    tileset_info = hgbi.tileset_info(filename)
    # print("tileset chromsizes:", tileset_info['chromsizes'])
    tsinfo_chromsizes = set([(str(chrom), str(size)) for chrom, size in tileset_info['chromsizes']])
    # print("tsinfo_chromsizes:", tsinfo_chromsizes)

    chrom_info_tileset = None

    # check if we have a chrom sizes tileset that matches the coordsystem
    # of the input file
    if coord_system is not None and len(coord_system) > 0:
        try:
            chrom_info_tileset = tm.Tileset.objects.filter(
                    coordSystem=coord_system,
                    datatype='chromsizes')

            if len(chrom_info_tileset) > 1:
                raise CommandError("More than one available set of chromSizes"
                        + "for this coordSystem ({})".format(coord_system))

            chrom_info_tileset = chrom_info_tileset.first()
        except dce.ObjectDoesNotExist:
            chrom_info_tileset = None

    matches = []

    if chrom_info_tileset is None:
        # we haven't found chromsizes matching the coordsystem
        # go through every chromsizes file and see if we have a match
        for chrom_info_tileset in tm.Tileset.objects.filter(datatype='chromsizes'):
            chromsizes_set = set([tuple(t) for
                t in tcs.get_tsv_chromsizes(chrom_info_tileset.datafile.path)])

            matches += [(len(set.intersection(chromsizes_set, tsinfo_chromsizes)),
                chrom_info_tileset)]

            # print("chrom_info_tileset:", chromsizes_set)
            #print("intersection:", len(set.intersection(chromsizes_set, tsinfo_chromsizes)))
        #print("coord_system:", coord_system)
    else:
        # a set of chromsizes was provided
        chromsizes_set = set([tuple(t) for
            t in tcs.get_tsv_chromsizes(chrom_info_tileset.datafile.path)])
        matches += [(len(set.intersection(chromsizes_set, tsinfo_chromsizes)),
            chrom_info_tileset)]

    # matches that overlap some chromsizes with the bigwig file
    overlap_matches = [m for m in matches if m[0] > 0]

    if len(overlap_matches) == 0:
        raise CommandError("No chromsizes available which match the chromosomes in this bigwig"
                + "See http://docs.higlass.io/data_preparation.html#bigwig-files "
                + "for more information"
                )

    if len(overlap_matches) > 1:
        raise CommandError("Multiple matching coordSystems:"
                + "See http://docs.higlass.io/data_preparation.html#bigwig-files "
                + "for more information",
                ["({} [{}])".format(t[1].coordSystem, t[0]) for t in overlap_matches])

    if (coord_system is not None
            and len(coord_system) > 0
            and overlap_matches[0][1].coordSystem != coord_system):
        raise CommandError("Matching chromosome sizes (coordSystem: {}) do not "
            + "match the specified coordinate sytem ({}). "
            + "Either omit the coordSystem or specify a matching one."
            + "See http://docs.higlass.io/data_preparation.html#bigwig-files "
            + "for more information".format(overlap_matches[0][1].coordSystem, coord_system))

    if (coord_system is not None
            and len(coord_system) > 0
            and overlap_matches[0][1].coordSystem == coord_system):
        print("Using coordinates for coordinate system: {}".format(coord_system))

    if coord_system is None or len(coord_system) == 0:
        print("No coordinate system specified, but we found matching "
            + "chromsizes. Using coordinate system {}."
            .format(overlap_matches[0][1].coordSystem))

    return overlap_matches[0][1].coordSystem

class Command(BaseCommand):
    def add_arguments(self, parser):
        # TODO: filename, datatype, fileType and coordSystem should
        # be checked to make sure they have valid values
        # for now, coordSystem2 should take the value of coordSystem
        # if the datatype is matrix
        # otherwise, coordSystem2 should be empty
        parser.add_argument('--filename', type=str)
        parser.add_argument('--indexfile', type=str)
        parser.add_argument('--datatype', type=str)
        parser.add_argument('--filetype', type=str)
        parser.add_argument('--coordSystem', default='', type=str)
        parser.add_argument('--coordSystem2', default='', type=str)
        # parser.add_argument('--coord', default='hg19', type=str)
        parser.add_argument('--uid', type=str)
        parser.add_argument('--name', type=str)
        parser.add_argument('--project-name', type=str, default='')

        # Named (optional) arguments
        parser.add_argument(
            '--no-upload',
            action='store_true',
            dest='no_upload',
            default=False,
            help='Skip upload',
        )

    def handle(self, *args, **options):
        ingest(**options)
