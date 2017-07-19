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


def get_domains_by_loc(
    cooler_file,
    loci,
    dim=64,
    balanced=False,
    zoomout_level=0,
    minSize=100000,
    maxSize=10000000,
    padding=10,  # Percent padding, e.g., 10 = 10% padding (5% per side)
    percentile=100,  # Percentile clip, e.g., 99 = 99-percentile is max
    ignore_diags=0  # Number of diagonals to be ignored
):
    with h5py.File(cooler_file, 'r') as f:
        c = get_cooler(f, zoomout_level)

        resolution = c.info['bin-size']

        domains = []

        # Restrict padding to be [0, 100]%
        padding = min(100, max(0, padding)) / 100

        for index, locus in enumerate(loci):
            chrom = locus[0]
            if not locus[0].startswith('chr'):
                chrom = 'chr{}'.format(locus[0])

            start = locus[1]
            end = locus[2]

            futureMap = np.zeros((dim, dim), float)

            bin_offset = c.offset(chrom)
            start_bin = bin_offset + int(np.rint(float(start) / resolution))
            end_bin = bin_offset + int(np.rint(float(end) / resolution)) + 1
            max_bin = bin_offset + int(
                np.rint(c.chromsizes[chrom] / resolution)
            )
            dom_len = end_bin - start_bin
            abs_padding = int(np.rint((dom_len / 2) * padding))

            if max_bin - end_bin > abs_padding and start_bin > abs_padding:
                start_bin -= abs_padding
                end_bin += abs_padding

            dom_len = end_bin - start_bin

            data = c.matrix(
                as_pixels=True, balance=False, max_chunk=np.inf
            )[start_bin:end_bin, start_bin:end_bin]

            bins = c.bins(convert_enum=False)[['weight']]
            data = cooler.annotate(data, bins, replace=False)
            data['rel_bin1'] = data['bin1_id'] - start_bin
            data['rel_bin2'] = data['bin2_id'] - start_bin

            data['balanced'] = (
                data['count'] * data['weight1'] * data['weight2']
            )
            data['idx1'] = (data['rel_bin1'] * dom_len) + data['rel_bin2']
            data['idx2'] = (data['rel_bin2'] * dom_len) + data['rel_bin1']

            singleMap = np.zeros(dom_len**2, dtype=np.float32)
            singleMap[data['idx1']] = np.nan_to_num(data['balanced'])
            singleMap[data['idx2']] = np.nan_to_num(data['balanced'])
            singleMap = singleMap.reshape((dom_len, dom_len))

            futureMap = futureMap + zoomArray(
                singleMap, futureMap.shape, order=1
            ).copy()

            # Normalize min
            min_val = np.min(futureMap)
            futureMap -= min_val

            # Normalize max
            if ignore_diags > 0:
                futureMap[np.diag_indices(dim)] = 0

                if ignore_diags > 1:
                    for i in range(1, ignore_diags):
                        idx = np.diag_indices(dim)
                        print(i, ((idx[0] + i)[:-i], (idx[1] + i)[:-i]))

                        futureMap[((idx[0] - i)[i:], (idx[1])[i:])] = 0
                        futureMap[((idx[0] + i)[:-i], (idx[1])[:-i])] = 0

            max_val = np.percentile(futureMap, percentile)
            futureMap = np.clip(futureMap, 0, max_val)

            if max_val > 0:
                futureMap /= max_val

            domains.append(futureMap)

    return domains


def get_frag_by_loc(
    cooler_file,
    loci,
    is_rel=True,
    dim=22,
    balanced=True,
    zoomout_level=0,
    padding=None
):
    with h5py.File(cooler_file, 'r') as f:
        c = get_cooler(f, zoomout_level)

        fragments = collect_frags(c, loci, is_rel, dim, balanced, padding)

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


def collect_frags(c, loci, is_rel=False, dim=22, balanced=True, padding=None):
    chr_info = get_chrom_names_cumul_len(c)
    cis_only = check_cis_only(loci)

    if cis_only and c.info['bin-size'] >= 4000:
        # Sort loci by chromosome
        loci.sort(key=lambda locus: locus[0])

        fragments = np.zeros((len(loci), dim, dim))

        k = 0
        last_chrom = None
        pixels = None
        for locus in loci:
            chrom = 'chr{}'.format(loci[k][0])

            if (
                not chrom == last_chrom or
                pixels is None
            ):
                pixels = c.matrix(balance=balanced).fetch(chrom)

            fragments[k] = get_cis_frag(
                c,
                chr_info,
                pixels,
                locus[1],  # start 1
                locus[2],  # end 1
                locus[4],  # start 2
                locus[5],  # end 2,
                balanced=balanced,
                dim=dim,
                padding=padding
            )

            k += 1

            last_chrom = chrom

    else:
        if is_rel:
            loci = rel_2_abs_loci(loci, chr_info)

        fragments = np.zeros((len(loci), dim, dim))

        k = 0
        for locus in loci:
            fragments[k] = get_frag(
                c,
                chr_info,
                *locus,
                balanced=balanced,
                dim=dim,
                padding=padding
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
    c,
    chr_info,
    start_pos_1,
    end_pos_1,
    start_pos_2,
    end_pos_2,
    padding=10,
    normalize=True,
    balanced=True,
    dim=22
):
    resolution = c.info['bin-size']

    center_start_bin_1 = int(np.rint(float(start_pos_1) / resolution))
    center_start_bin_2 = int(np.rint(float(start_pos_2) / resolution))
    center_end_bin_1 = int(np.rint(float(end_pos_1) / resolution))
    center_end_bin_2 = int(np.rint(float(end_pos_2) / resolution))

    padding_1 = int((dim - (center_end_bin_1 - center_start_bin_1)) / 2)
    padding_2 = int((dim - (center_end_bin_2 - center_start_bin_2)) / 2)

    # abs_coord_2_bin(...) returns the inclusive bin ID but in the python world
    # the end position is always exclusive
    start_bin_1 = max(abs_coord_2_bin(c, start_pos_1, chr_info) - padding_1, 0)
    start_bin_2 = max(abs_coord_2_bin(c, start_pos_2, chr_info) - padding_2, 0)
    end_bin_1 = abs_coord_2_bin(c, end_pos_1, chr_info) + padding_1
    end_bin_2 = abs_coord_2_bin(c, end_pos_2, chr_info) + padding_2

    real_dim = abs(start_bin_1 - end_bin_1)
    if real_dim < dim:
        end_bin_1 += dim - real_dim

    real_dim = abs(start_bin_2 - end_bin_2)
    if real_dim < dim:
        end_bin_2 += dim - real_dim

    out = c.matrix(balance=balanced)[
        start_bin_1:end_bin_1, start_bin_2:end_bin_2
    ][0:dim, 0:dim]

    # Store low quality bins
    low_quality_bins = np.where(np.isnan(out))

    # Assign 0 for now to avoid influencing the max values
    out[low_quality_bins] = 0

    max_val = np.max(out)
    if normalize and max_val > 0:
        out = out / max_val

    # Reassign a special value to cells with low quality
    out[low_quality_bins] = -1

    return out


def get_cis_frag(
    c,
    chr_info,
    pixels,
    start_pos_1,
    end_pos_1,
    start_pos_2,
    end_pos_2,
    normalize=True,
    balanced=True,
    dim=22,
    padding=10
):
    resolution = c.info['bin-size']

    center_start_bin_1 = int(np.rint(float(start_pos_1) / resolution))
    center_start_bin_2 = int(np.rint(float(start_pos_2) / resolution))
    center_end_bin_1 = int(np.rint(float(end_pos_1) / resolution))
    center_end_bin_2 = int(np.rint(float(end_pos_2) / resolution))

    padding_1 = int((dim - (center_end_bin_1 - center_start_bin_1)) / 2)
    padding_2 = int((dim - (center_end_bin_2 - center_start_bin_2)) / 2)

    start_bin_1 = max(
        center_start_bin_1 - padding_1, 0
    )
    start_bin_2 = max(
        center_start_bin_2 - padding_2, 0
    )
    end_bin_1 = min(
        center_end_bin_1 + padding_1,
        pixels.shape[0]
    )
    end_bin_2 = min(
        center_end_bin_2 + padding_2,
        pixels.shape[1]
    )

    real_dim = abs(start_bin_1 - end_bin_1)
    if real_dim < dim:
        diff = dim - real_dim

        if end_bin_1 + diff < pixels.shape[0]:
            end_bin_1 += diff
        elif start_bin_1 - diff > 0:
            start_bin_1 -= diff

    real_dim = abs(start_bin_2 - end_bin_2)
    if real_dim < dim:
        diff = dim - real_dim

        if end_bin_2 + diff < pixels.shape[1]:
            end_bin_2 += diff
        elif start_bin_2 - diff > 0:
            start_bin_2 -= diff

    out = pixels[start_bin_1:end_bin_1, start_bin_2:end_bin_2][0:dim, 0:dim]

    # Store low quality bins
    low_quality_bins = np.where(np.isnan(out))

    # Assign 0 for now to avoid influencing the max values
    out[low_quality_bins] = 0

    max_val = np.max(out)
    if normalize and max_val > 0:
        out = out / max_val

    # Reassign a special value to cells with low quality
    out[low_quality_bins] = -1

    return out


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
