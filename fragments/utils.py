import cooler
import h5py
import logging
import numpy as np
import pandas as pd

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
        offset = chr_info[2][chr_info[3]['chr%s' % str(chr)]]

        return (offset + x, offset + y)

    def absolutize_tuple(tuple):
        return (
            absolutize(*tuple[0:3]) +
            absolutize(*tuple[3:6])
        )

    return map(absolutize_tuple, loci)


def get_cooler(f, zoomout_level=-1):
    if zoomout_level >= 0:
        zoom_levels = np.array(f.keys(), dtype=int)

        max_zoom = np.max(zoom_levels)
        min_zoom = np.min(zoom_levels)

        zoom_level = max_zoom - zoomout_level

        try:
            if (zoom_level >= min_zoom and zoom_level <= max_zoom):
                c = cooler.Cooler(f[str(zoom_level)])
            else:
                c = cooler.Cooler(f['0'])
        except Exception as e:
            c = cooler.Cooler(f)
    else:
        c = cooler.Cooler(f)

    return c


def get_frag_by_loc(
    cooler_file,
    loci,
    is_rel=True,
    dim=22,
    balanced=True,
    zoomout_level=-1
):
    with h5py.File(cooler_file, 'r') as f:
        c = get_cooler(f, zoomout_level)

        fragments = collect_frags(c, loci, is_rel, dim, balanced)

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


def collect_frags(c, loci, is_rel=False, dim=22, balanced=True):
    chr_info = get_chrom_names_cumul_len(c)

    if is_rel:
        loci = rel_2_abs_loci(loci, chr_info)

    fragments = np.zeros((len(loci), dim, dim))

    k = 0
    for locus in loci:
        fragments[k] = get_frag(
            c, chr_info, *locus, balanced=balanced, dim=dim
        )

        if max > 0 and k >= max:
            break

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
    # abs_coord_2_bin(...) returns the inclusive bin ID but in the python world
    # the end position is always exclusive
    start_bin_1 = max(abs_coord_2_bin(c, start_pos_1, chr_info) - padding, 0)
    start_bin_2 = max(abs_coord_2_bin(c, start_pos_2, chr_info) - padding, 0)
    end_bin_1 = abs_coord_2_bin(c, end_pos_1, chr_info) + padding + 1
    end_bin_2 = abs_coord_2_bin(c, end_pos_2, chr_info) + padding + 1

    real_dim = min(abs(start_bin_1 - end_bin_1), abs(start_bin_2 - end_bin_2))

    if real_dim < dim:
        diff = dim - real_dim
        end_bin_1 += diff
        end_bin_2 += diff

    pixels = c.matrix(
        as_pixels=True, max_chunk=np.inf, balance=balanced
    )[start_bin_1:end_bin_1, start_bin_2:end_bin_2]

    pixels['id_1'] = pixels['bin1_id'] - start_bin_1
    pixels['id_2'] = pixels['bin2_id'] - start_bin_2

    out = np.zeros(dim**2, dtype=np.float)

    accessor = 'count'

    if balanced:
        accessor = 'balanced'
    for index, row in pixels.iterrows():
        try:
            out[
                row['id_1'].astype(np.uint32) * dim +
                row['id_2'].astype(np.uint32)
            ] = row[accessor]
        except IndexError:
            continue

    # Store low quality bins
    low_quality_bins = np.where(np.isnan(out))

    # Assign 0 for now to avoid influencing the max values
    out[low_quality_bins] = 0

    max_val = np.max(out)
    if normalize and max_val > 0:
        out = out / max_val

    # Reassign a special value to cells with low quality
    out[low_quality_bins] = -1

    return out.reshape(dim, dim)[:dim, :dim]
