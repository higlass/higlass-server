from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import cooler
import h5py
import logging
import numpy as np
import pandas as pd

from scipy.ndimage.interpolation import zoom

logger = logging.getLogger(__name__)


# Methods

def get_chrom_names_cumul_len(c):
    '''
    Get the chromosome names and cumulative lengths:

    Args:

    c (Cooler): A cooler file

    Return:

    (names, sizes, lengths) -> (list(string), dict, np.array(int))
    '''

    chrom_sizes = {}
    chrom_cum_lengths = [0]
    chrom_ids = {}
    chroms = []

    k = 0

    for chrom in c.chroms():
        (name, length) = chrom.as_matrix()[0]

        chroms += [name]
        chrom_cum_lengths += [chrom_cum_lengths[-1] + length]
        chrom_sizes[name] = length
        chrom_ids[name] = k

        k += 1

    return (chroms, chrom_sizes, np.array(chrom_cum_lengths), chrom_ids)


def get_intra_chr_loops_from_looplist(loop_list, chr=0):
    loops = pd.DataFrame.from_csv(loop_list, sep='\t', header=0)

    s_chr = str(chr)

    if chr > 0:
        loops = loops[loops['chr2'] == s_chr].loc[s_chr]

    chrs = np.zeros((loops.shape[0], 2), dtype=object)

    chrs[:, 0] = loops['chr2']
    chrs[:, 1] = loops['chr2']

    return (loops.as_matrix()[:, [0, 1, 3, 4]], chrs)


def rel_2_abs_loci(loci, chr_info):
    '''
    chr_info[0] = chromosome names
    chr_info[1] = chromosome lengths
    chr_info[2] = cumulative lengths
    chr_info[3] = chromosome ids
    '''
    def absolutize(chr, x, y):
        chrom = str(chr)

        if not chrom.startswith('chr'):
            chrom = 'chr{}'.format(chrom)

        offset = chr_info[2][chr_info[3][chrom]]

        return (offset + x, offset + y)

    def absolutize_tuple(tuple):
        return (
            absolutize(*tuple[0:3]) +
            absolutize(*tuple[3:6])
        )

    return list(map(absolutize_tuple, loci))


def get_cooler(f, zoomout_level=0):
    c = None

    try:
        zoom_levels = np.array(list(f.keys()), dtype=int)

        max_zoom = np.max(zoom_levels)
        min_zoom = np.min(zoom_levels)

        zoom_level = max_zoom - max(zoomout_level, 0)

        if (zoom_level >= min_zoom and zoom_level <= max_zoom):
            c = cooler.Cooler(f[str(zoom_level)])
        else:
            c = cooler.Cooler(f['0'])

        return c
    except Exception as e:
        logger.error(e)
        pass  # failed loading zoomlevel of cooler file

    try:
        c = cooler.Cooler(f)
    except Exception as e:
        logger.error(e)

    return c


def get_frag_by_loc(
    cooler_file,
    loci,
    dim,
    zoomout_level=0,
    balanced=True,
    padding=None,
    percentile=100.0,
    ignore_diags=0
):
    with h5py.File(cooler_file, 'r') as f:
        c = get_cooler(f, zoomout_level)

        # Calculate the offsets once
        resolution = c.info['bin-size']
        chromsizes = np.ceil(c.chromsizes / resolution).astype(int)
        offsets = np.cumsum(chromsizes) - chromsizes

        fragments = collect_frags(
            c,
            loci,
            dim,
            resolution,
            offsets,
            padding=padding,
            balanced=balanced,
            percentile=percentile,
            ignore_diags=ignore_diags
        )

    return fragments


def calc_measure_dtd(matrix, locus):
    '''
    Calculate the distance to the diagonal
    '''
    return np.abs(locus['end1'] - locus['start2'])


def calc_measure_size(matrix, locus, bin_size=1):
    '''
    Calculate the size of the snippet
    '''
    return (
        np.abs(locus['start1'] - locus['end1']) *
        np.abs(locus['start2'] - locus['end2'])
    ) / bin_size


def calc_measure_noise(matrix):
    '''
    Estimate the noise level of the input matrix using the standard deviation
    '''
    low_quality_bins = np.where(matrix == -1)

    # Assign 0 for now to avoid influencing the standard deviation
    matrix[low_quality_bins] = 0

    noise = np.std(matrix)

    # Ressign -1 to low quality bins
    matrix[low_quality_bins] = -1

    return noise


def calc_measure_sharpness(matrix):
    low_quality_bins = np.where(matrix == -1)

    # Assign 0 for now to avoid influencing the variance caluclation
    matrix[low_quality_bins] = 0

    sum = np.sum(matrix)
    sum = sum if sum > 0 else 1
    dim = matrix.shape[0]

    middle = (dim - 1) / 2
    m = dim

    if dim % 2 == 0:
        middle = (dim - 2) / 2
        m = dim / 2

    var = 0

    for i in range(dim):
        for j in range(dim):

            var += (
                ((i - (middle + i // m)) ** 2 + (j - middle + i // m) ** 2) *
                matrix[i, j]
            )

    # Ressign -1 to low quality bins
    matrix[low_quality_bins] = -1

    return var / sum


def get_bin_size(cooler_file, zoomout_level=-1):
    with h5py.File(cooler_file, 'r') as f:
        c = get_cooler(f, zoomout_level)

        return c.util.get_binsize()


def check_cis_only(loci):
    loci = np.array(loci)
    return np.all(loci[0:, 0] == loci[0:, 3])


def collect_frags(
    c,
    loci,
    dim,
    resolution,
    offsets,
    padding=0,
    balanced=True,
    percentile=100.0,
    ignore_diags=0
):
    fragments = np.zeros((len(loci), dim, dim))

    k = 0
    for locus in loci:
        fragments[k] = get_frag(
            c,
            resolution,
            offsets,
            *locus[:6],
            width=dim,
            padding=padding,
            balanced=balanced,
            percentile=percentile,
            ignore_diags=ignore_diags
        )

        k += 1

    return fragments


def get_chrom(abs_pos, chr_info=None, c=None):
    if chr_info is None:
        try:
            chr_info = get_chrom_names_cumul_len(c)
        except:
            return None

    try:
        chr_id = np.flatnonzero(chr_info[2] > abs_pos)[0] - 1
    except IndexError:
        return None

    return chr_info[0][chr_id]


def get_chroms(abs_pos, chr_info=None, cooler_file=None, zoomout_level=-1):
    chroms = np.zeros((abs_pos.shape[0], 2), dtype=object)

    if chr_info is None:
        with h5py.File(cooler_file, 'r') as f:
            c = get_cooler(f, zoomout_level)
            chr_info = get_chrom_names_cumul_len(c)

    i = 0
    for pos in abs_pos:
        chroms[i] = get_chrom(pos, chr_info)
        i += 1

    return chroms


def rel_loci_2_obj(loci_rel_chroms):
    loci = []

    i = 0
    for locus in loci_rel_chroms:
        loci.append({
            'chrom1': loci_rel_chroms[i, 0],
            'start1': loci_rel_chroms[i, 1],
            'end1': loci_rel_chroms[i, 2],
            'strand1': (
                'coding' if loci_rel_chroms[i, 1] < loci_rel_chroms[i, 2] else
                'noncoding'
            ),
            'chrom2': loci_rel_chroms[i, 3],
            'start2': loci_rel_chroms[i, 4],
            'end2': loci_rel_chroms[i, 5],
            'strand2': (
                'coding' if loci_rel_chroms[i, 1] < loci_rel_chroms[i, 2] else
                'noncoding'
            )
        })
        i += 1

    return loci


def abs_coord_2_bin(c, pos, chr_info):
    try:
        chr_id = np.flatnonzero(chr_info[2] > pos)[0] - 1
    except IndexError:
        return c.info['nbins']

    chrom = chr_info[0][chr_id]
    relPos = pos - chr_info[2][chr_id]

    return c.offset((chrom, relPos, chr_info[1][chrom]))


def get_frag(
    c: cooler.api.Cooler,
    resolution: int,
    offsets: pd.core.series.Series,
    chrom1: str,
    start1: int,
    end1: int,
    chrom2: str,
    start2: int,
    end2: int,
    width: int = 22,
    height: int = -1,
    padding: int = 10,
    normalize: bool = True,
    balanced: bool = True,
    percentile: float = 100.0,
    ignore_diags: int = 0
) -> np.ndarray:
    """
    Retrieves a matrix fragment.

    Args:
        c:
            Cooler object.
        chrom1:
            Chromosome 1. E.g.: `1` or `chr1`.
        start1:
            First start position in base pairs relative to `chrom1`.
        end1:
            First end position in base pairs relative to `chrom1`.
        chrom2:
            Chromosome 2. E.g.: `1` or `chr1`.
        start2:
            Second start position in base pairs relative to `chrom2`.
        end2:
            Second end position in base pairs relative to `chrom2`.
        offsets:
            Pandas Series of chromosome offsets in bins.
        width:
            Width of the fragment in pixels.
        height:
            Height of the fragments in pixels. If `-1` `height` will equal
            `width`. Defaults to `-1`.
        padding: Percental padding related to the dimension of the fragment.
            E.g., 10 = 10% padding (5% per side). Defaults to `10`.
        normalize:
            If `True` the fragment will be normalized to [0, 1].
            Defaults to `True`.
        balanced:
            If `True` the fragment will be balanced using Cooler.
            Defaults to `True`.
        percentile:
            Percentile clip. E.g., For 99 the maximum will be
            capped at the 99-percentile. Defaults to `100.0`.
        ignore_diags:
            Number of diagonals to be ignored, i.e., set to 0.
            Defaults to `0`.

    Returns:

    """

    if height is -1:
        height = width

    # Restrict padding to be [0, 100]%
    padding = min(100, max(0, padding)) / 100

    # Normalize chromosome names
    if not chrom1.startswith('chr'):
        chrom1 = 'chr{}'.format(chrom1)
    if not chrom2.startswith('chr'):
        chrom2 = 'chr{}'.format(chrom2)

    # Get chromosome offset
    offset1 = offsets[chrom1]
    offset2 = offsets[chrom2]

    start_bin1 = offset1 + int(round(float(start1) / resolution))
    end_bin1 = offset1 + int(round(float(end1) / resolution)) + 1

    start_bin2 = offset2 + int(round(float(start2) / resolution))
    end_bin2 = offset2 + int(round(float(end2) / resolution)) + 1

    # Apply percental padding
    padding1 = int(round(((end_bin1 - start_bin1) / 2) * padding))
    padding2 = int(round(((end_bin2 - start_bin2) / 2) * padding))
    start_bin1 -= padding1
    start_bin2 -= padding2
    end_bin1 += padding1
    end_bin2 += padding2

    # Get the size of the region
    dim1 = end_bin1 - start_bin1
    dim2 = end_bin2 - start_bin2

    # Get additional absolute padding if needed
    padding1 = 0
    if dim1 < width:
        padding1 = int((width - dim1) / 2)
        start_bin1 -= padding1
        end_bin1 += padding1

    padding2 = 0
    if dim2 < height:
        padding2 = int((height - dim2) / 2)
        start_bin2 -= padding2
        end_bin2 += padding2

    # In case the final dimension does not math the desired domension we
    # increase the end bin. This can be caused when the padding is not
    # divisable by 2, since the padding is rounded to the nearest integer.
    abs_dim1 = abs(start_bin1 - end_bin1)
    if abs_dim1 < width:
        end_bin1 += width - abs_dim1
        abs_dim1 = width

    abs_dim2 = abs(start_bin2 - end_bin2)
    if abs_dim2 < height:
        end_bin2 += height - abs_dim2
        abs_dim2 = height

    # Get the data
    data = c.matrix(
        as_pixels=True, balance=False, max_chunk=np.inf
    )[start_bin1:end_bin1, start_bin2:end_bin2]

    # Annotate pixels for balancing
    bins = c.bins(convert_enum=False)[['weight']]
    data = cooler.annotate(data, bins, replace=False)

    # Calculate relative bin IDs
    rel_bin1 = np.add(data['bin1_id'].values, -start_bin1)
    rel_bin2 = np.add(data['bin2_id'].values, -start_bin2)

    # Balance counts
    if balanced:
        values = data['count'].values.astype(np.float32)
        values *= data['weight1'].values * data['weight2'].values
    else:
        values = data['count'].values

    # Get pixel IDs for the upper triangle
    idx1 = np.add(np.multiply(rel_bin1, abs_dim1), rel_bin2)

    # Mirror matrix
    idx2_1 = np.add(data['bin2_id'].values, -start_bin1)
    idx2_2 = np.add(data['bin1_id'].values, -start_bin2)
    idx2 = np.add(np.multiply(idx2_1, abs_dim1), idx2_2)
    validBins = np.where((idx2_1 < abs_dim1) & (idx2_2 >= 0))

    # Ignore diagonals
    if ignore_diags > 0:
        diags_start_idx = np.min(
            np.where(data['bin1_id'].values == data['bin2_id'].values)
        )
        diags_start_row = rel_bin1[diags_start_idx] - rel_bin2[diags_start_idx]

    # Copy pixel values onto the final array
    frag = np.zeros(abs_dim1 * abs_dim2, dtype=np.float32)
    frag[idx1] = values
    frag[idx2[validBins]] = values[validBins]
    frag = frag.reshape((abs_dim1, abs_dim2))

    # Store low quality bins
    low_quality_bins = np.where(np.isnan(frag))

    # Assign 0 for now to avoid influencing the max values
    frag[low_quality_bins] = 0

    # Scale array if needed
    scaled = False
    scale_x = width / frag.shape[0]
    if frag.shape[0] > width or frag.shape[1] > height:
        scaledFrag = np.zeros((width, height), float)
        frag = scaledFrag + zoomArray(
            frag, scaledFrag.shape, order=1
        )
        scaled = True

    # Normalize by minimum
    min_val = np.min(frag)
    frag -= min_val

    # Remove diagonals
    if ignore_diags > 0:
        if width == height:
            scaled_row = int(np.rint(diags_start_row / scale_x))

            for i in range(scaled_row, ignore_diags + scaled_row):
                idx = np.diag_indices(width)

                if i == 0:
                    frag[np.diag_indices(width)] = 0
                else:
                    frag[((idx[0] - i)[i:], (idx[1])[i:])] = 0
                    frag[((idx[0] + i)[:-i], (idx[1])[:-i])] = 0
        else:
            logger.warn(
                'Ignoring the diagonal only supported for squared features'
            )

    # Normalize by maximum
    max_val = np.percentile(frag, percentile)
    frag = np.clip(frag, 0, max_val)

    if max_val > 0:
        frag /= max_val

    if not scaled:
        # Recover low quality bins
        frag[low_quality_bins] = -1

    return frag


def zoomArray(
    inArray, finalShape, sameSum=False, zoomFunction=zoom, **zoomKwargs
):
    """
    Normally, one can use scipy.ndimage.zoom to do array/image rescaling.
    However, scipy.ndimage.zoom does not coarsegrain images well. It basically
    takes nearest neighbor, rather than averaging all the pixels, when
    coarsegraining arrays. This increases noise. Photoshop doesn't do that, and
    performs some smart interpolation-averaging instead.

    If you were to coarsegrain an array by an integer factor, e.g. 100x100 ->
    25x25, you just need to do block-averaging, that's easy, and it reduces
    noise. But what if you want to coarsegrain 100x100 -> 30x30?

    Then my friend you are in trouble. But this function will help you. This
    function will blow up your 100x100 array to a 120x120 array using
    scipy.ndimage zoom Then it will coarsegrain a 120x120 array by
    block-averaging in 4x4 chunks.

    It will do it independently for each dimension, so if you want a 100x100
    array to become a 60x120 array, it will blow up the first and the second
    dimension to 120, and then block-average only the first dimension.

    Parameters
    ----------

    inArray: n-dimensional numpy array (1D also works)
    finalShape: resulting shape of an array
    sameSum: bool, preserve a sum of the array, rather than values.
             by default, values are preserved
    zoomFunction: by default, scipy.ndimage.zoom. You can plug your own.
    zoomKwargs:  a dict of options to pass to zoomFunction.
    """
    inArray = np.asarray(inArray, dtype=np.double)
    inShape = inArray.shape
    assert len(inShape) == len(finalShape)
    mults = []  # multipliers for the final coarsegraining
    for i in range(len(inShape)):
        if finalShape[i] < inShape[i]:
            mults.append(int(np.ceil(inShape[i] / finalShape[i])))
        else:
            mults.append(1)
    # shape to which to blow up
    tempShape = tuple([i * j for i, j in zip(finalShape, mults)])

    # stupid zoom doesn't accept the final shape. Carefully crafting the
    # multipliers to make sure that it will work.
    zoomMultipliers = np.array(tempShape) / np.array(inShape) + 0.0000001
    assert zoomMultipliers.min() >= 1

    # applying zoom
    rescaled = zoomFunction(inArray, zoomMultipliers, **zoomKwargs)

    for ind, mult in enumerate(mults):
        if mult != 1:
            sh = list(rescaled.shape)
            assert sh[ind] % mult == 0
            newshape = sh[:ind] + [sh[ind] // mult, mult] + sh[ind + 1:]
            rescaled.shape = newshape
            rescaled = np.mean(rescaled, axis=ind + 1)
    assert rescaled.shape == finalShape

    if sameSum:
        extraSize = np.prod(finalShape) / np.prod(inShape)
        rescaled /= extraSize
    return rescaled
