import csv
import h5py
import logging
import numpy as np
import pandas as pd

from fragments.utils import get_cooler

logger = logging.getLogger(__name__)

def chromsizes_array_to_series(chromsizes):
    '''
    Convert an array of [[chrname, size]...] values to a series
    indexed by chrname with size values
    '''
    chrnames = [c[0] for c in chromsizes]
    chrvalues = [c[1] for c in chromsizes]

    return pd.Series(np.array([int(c) for c in chrvalues]), index=chrnames)

def get_multivec_chromsizes(filename):
    '''
    Get a list of chromosome sizes from this [presumably] multivec
    file.

    Parameters:
    -----------
    filename: string
        The filename of the multivec file

    Returns
    -------
    chromsizes: [(name:string, size:int), ...]
        An ordered list of chromosome names and sizes
    '''
    with h5py.File(filename, 'r') as f:
        try:
            chrom_names = [t.decode('utf-8') for t in f['chroms']['name'][:]]
            chrom_lengths = f['chroms']['length'][:]

            return zip(chrom_names, chrom_lengths)
        except Exception as e:
            logger.exception(e)
            raise Exception( 'Error retrieving multivec chromsizes')

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
            raise Exception('Yikes... Couldn~\'t init cooler files 😵')

        try:
            data = []
            for chrom, size in c.chromsizes.iteritems():
                data.append([chrom, size])
            return data
        except Exception as e:
            logger.error(e)
            raise Exception( 'Cooler file has no `chromsizes` attribute 🤔')

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

