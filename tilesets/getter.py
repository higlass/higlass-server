from __future__ import division, print_function

import numpy as np
import pandas as pd
import cooler
import h5py
import logging

logger = logging.getLogger(__name__)

TILE_SIZE = 256

CHROM_SIZES = cooler.read_chromsizes(
    'http://s3.amazonaws.com/pkerp/data/hg19/chromInfo.txt'
)
CHROMS = list(CHROM_SIZES.keys())
CHROM_IDS = dict(zip(CHROMS, range(len(CHROMS))))
CHROM_CUM_LEN = np.r_[0, np.cumsum(CHROM_SIZES)]


def abs_coord_2_bin(c, abs_pos):
    """Get bin ID from absolute coordinates.

    Args:
        c (Cooler): Cooler instance of a .cool file.
        abs_pos (int): Absolute coordinate to be translated.

    Returns:
        int: Bin number.
    """

    try:
        chr_id = np.flatnonzero(CHROM_CUM_LEN > abs_pos)[0] - 1
    except IndexError:
        return c.info['nbins']

    chrom = CHROMS[chr_id]
    rel_pos = abs_pos - CHROM_CUM_LEN[chr_id]

    return c.offset((chrom, rel_pos, CHROM_SIZES[chrom]))


def get_data(f, zoom_level, start_pos_1, end_pos_1, start_pos_2, end_pos_2):
    """Get balanced pixel data.

    Args:
        f (File): File pointer to a .cool filer.
        zoom_level (int): Test.
        start_pos_1 (int): Test.
        end_pos_1 (int): Test.
        start_pos_2 (int): Test.
        end_pos_2 (int): Test.

    Returns:
        DataFrame: Annotated cooler pixels.
    """

    c = cooler.Cooler(f[str(zoom_level)])

    i0 = abs_coord_2_bin(c, start_pos_1)
    i1 = abs_coord_2_bin(c, end_pos_1)
    j0 = abs_coord_2_bin(c, start_pos_2) + 1
    j1 = abs_coord_2_bin(c, end_pos_2) + 1

    pixels = c.matrix(as_pixels=True, max_chunk=np.inf)[i0:i1, j0:j1]

    if not len(pixels):
        return pd.DataFrame(columns=['genome_start', 'genome_end', 'balanced'])

    lo = min(i0, j0)
    hi = max(i1, j1)

    bins = c.bins()[['chrom', 'start', 'end', 'weight']][lo:hi]
    bins['chrom'] = bins['chrom'].cat.codes

    pixels = cooler.annotate(pixels, bins)
    pixels['genome_start'] = CHROM_CUM_LEN[pixels['chrom1']] + pixels['start1']
    pixels['genome_end'] = CHROM_CUM_LEN[pixels['chrom2']] + pixels['end2']
    pixels['balanced'] = (
        pixels['count'] * pixels['weight1'] * pixels['weight2']
    )

    return pixels[['genome_start', 'genome_end', 'balanced']]


def get_info(file_path):
    """Get information of a cooler file.

    Args:
        file_path (str): Path to a cooler file.

    Returns:
        dict: Dictionary containing basic information about the cooler file.
    """

    with h5py.File(file_path, 'r') as f:
        max_zoom = f.attrs.get('max-zoom')

        if max_zoom is None:
            logger.info('no zoom found')
            raise ValueError(
                'The `max_zoom` attribute is missing.'
            )

        total_length = int(CHROM_CUM_LEN[-1])
        max_zoom = f.attrs['max-zoom']
        bin_size = int(f[str(max_zoom)].attrs['bin-size'])

        max_width = bin_size * TILE_SIZE * 2**max_zoom

        info = {
            'min_pos': [0.0, 0.0],
            'max_pos': [total_length, total_length],
            'max_zoom': max_zoom,
            'max_width': max_width,
            'bins_per_dimension': TILE_SIZE,
        }

    return info
