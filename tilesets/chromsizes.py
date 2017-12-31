import csv
import h5py
import logging

from fragments.utils import get_cooler

logger = logging.getLogger(__name__)

def get_cooler_chromsizes(filename):
    '''
    Get a list of chromosome sizes from this [presumably] cooler
    file.

    Parameters:
    -----------
    filename: string
        The filename of the cooler file

    Returns
    -------
    chromsizes: [(name:string, size:int), ...]
        An ordered list of chromosome names and sizes
    '''
    with h5py.File(filename, 'r') as f:

        try:
            c = get_cooler(f)
        except Exception as e:
            logger.error(e)
            raise Exception('Yikes... Couldn~\'t init them cooler files 😵')

        try:
            data = []
            for chrom, size in c.chromsizes.iteritems():
                data.append([chrom, size])
            return data
        except Exception as e:
            logger.error(e)
            raise Exception( 'Them cooler files has no `chromsizes` attribute 🤔')

def get_tsv_chromsizes(filename):
    '''
    Get a list of chromosome sizes from this [presumably] tsv
    chromsizes file file.

    Parameters:
    -----------
    filename: string
        The filename of the tsv file

    Returns
    -------
    chromsizes: [(name:string, size:int), ...]
        An ordered list of chromosome names and sizes
    '''
    try:
        with open(filename, 'r') as f:
            reader = csv.reader(f, delimiter='\t')

            data = []
            for row in reader:
                data.append(row)
        return data
    except Exception as ex:
        logger.error(ex)

        err_msg = 'WHAT?! Could not load file %s. 😤 (%s)' % (
            filename, ex
        )

        raise Exception(err_msg)

