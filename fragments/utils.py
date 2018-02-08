from __future__ import (
    absolute_import, division, print_function, unicode_literals
)

import cooler
import h5py
import logging
import numpy as np
import pandas as pd
import sqlite3
import requests
import math

from hdbscan import HDBSCAN
from random import random
from io import BytesIO, StringIO
from PIL import Image
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.utils.extmath import cartesian
from scipy.ndimage.interpolation import zoom
from scipy.spatial.distance import cdist

from tilesets.models import Tileset

from imtiles import utils as imtu
from geotiles import utils as geotu

logger = logging.getLogger(__name__)


# Methods

def get_features(tile_set, zoom, x_from, x_to, y_fom, y_to):
    if (
        tile_set.filetype == 'bed2ddb' or
        tile_set.filetype == '2dannodb' or
        tile_set.filetype == 'imtiles'
    ):
        return imtu.get_features(
            tile_set.datafile.url, zoom, x_from, x_to, y_fom, y_to
        )
    elif tile_set.filetype == 'geodb':
        return geotu.get_features(
            tile_set.datafile.url, zoom, x_from, x_to, y_fom, y_to
        )

    return []


def cluster_fragments(
    tile_sets,
    zoom_level,
    x_from,
    x_to,
    y_from,
    y_to,
    width=1072,
    height=768,
    inset_disp_size_min=16,
    inset_disp_size_max=64,
    inset_thres=16,
    clust_rel_pad=0.0,
    clust_meth='grid'
):
    '''Cluster small regions within a larger region
    '''

    suported_cluster_methods = ['grid', 'density']

    if clust_meth not in suported_cluster_methods:
        raise ValueError(
            'Cluster method not supported. Choose between grid or density.'
        )

    supported_filetypes = ['bed2ddb', '2dannodb', 'geodb']

    if not all(
        tile_set.filetype in supported_filetypes for tile_set in tile_sets
    ):
        raise ValueError(
            'One or more tile sets are not supported. Only bed2ddb, '
            '2dannodb, and geodb are supported.'
        )

    # Assemble features
    inset_dims = []
    inset_aspect_ratio = []
    inset_size_min = math.inf
    inset_size_max = -math.inf
    inset_centroids = []

    data_to_view_scale = (x_to - x_from) / width

    feature_area_total = np.zeros([height, width])

    for tile_set in tile_sets:
        features = get_features(
            tile_set, zoom_level, x_from, x_to, y_from, y_to
        )

        for f in features:
            f_width = f[1] - f[0]
            f_height = f[3] - f[2]
            size = max(f_width, f_height) / data_to_view_scale

            d_x_1 = round(f[0] / data_to_view_scale)
            d_x_2 = round(f[1] / data_to_view_scale)
            d_y_1 = round(f[2] / data_to_view_scale)
            d_y_2 = round(f[3] / data_to_view_scale)

            feature_area_total[d_y_1:d_y_2, d_x_1:d_x_2] = 1

            if size <= inset_thres:
                inset_centroids.append(np.mean([f[0:2], f[2:4]], axis=1))
                inset_size_min = min(size, inset_size_min)
                inset_size_max = max(size, inset_size_max)
                inset_dims.append([f_width, f_height])
                inset_aspect_ratio.append(f_width / f_height)

    def lin_scl(v, d_from, d_to, r_from, r_to, is_clapped):
        return np.minimum(
            r_to if is_clapped else np.inf,
            np.maximum(
                r_from if is_clapped else -np.inf,
                (((v - d_from) / (d_to - d_from)) * (r_to - r_from)) + r_from
            )
        )

    inset_dims = np.array(inset_dims)
    inset_centroids = np.array(inset_centroids)

    try:
        inset_dim_max = np.maximum(inset_dims[:, 0], inset_dims[:, 1])
    except Exception as e:
        inset_dim_max = np.array([])

    inset_size_to_disp_scale = lin_scl(
        inset_dim_max,
        inset_size_min,
        inset_size_max,
        inset_disp_size_min,
        inset_disp_size_max,
        True
    ) / inset_dim_max
    inset_disp_size = (inset_dims.T * inset_size_to_disp_scale).T

    # View area
    view_area = width * height
    inset_disp_area = inset_disp_size[:, 0] * inset_disp_size[:, 1]
    inset_disp_area_total = np.sum(inset_disp_area)

    num_clust = 0

    if len(inset_centroids) > 0:
        config = {}

        if clust_meth == 'density':
            config['min_cluster_size'] = 5

        else:
            max_dim = max(width, height)
            config['width'] = width
            config['height'] = height
            config['clust_per_max'] = np.floor(
                max_dim / inset_disp_size_max / 4
            )

        labels, num_clust = cluster_points(inset_centroids, clust_meth, config)

        clust_density = compute_intra_cluster_density(
            inset_centroids / data_to_view_scale,
            inset_dims,
            inset_disp_area,
            labels,
            num_clust,
            feature_area_total,
            inset_disp_size_min=inset_disp_size_min,
            inset_disp_size_max=inset_disp_size_max,
            clust_rel_pad=clust_rel_pad
        )

    return {
        'clust_density': clust_density,
        'num_clust': int(num_clust),
        'num_insets': len(inset_centroids),
        'view_area': int(view_area),
        'feature_area_total': int(np.sum(feature_area_total)),
        'feature_stress': np.sum(feature_area_total) / view_area,
        'inset_disp_area_total': int(inset_disp_area_total),
        'inset_stress': inset_disp_area_total / view_area,
        'feature_area': feature_area_total
    }


def bbox_points(points):
    x_from = np.min(points[:, 0])
    x_to = np.max(points[:, 0])
    y_from = np.min(points[:, 1])
    y_to = np.max(points[:, 1])
    width = x_to - x_from
    height = y_to - y_from

    return (x_from, x_to, y_from, y_to, width, height)


def compute_intra_cluster_density(
    all_inset_centroids,
    all_inset_dims,
    all_inset_disp_area,
    labels,
    num_clust,
    feature_area_total,
    inset_disp_size_min=16,
    inset_disp_size_max=64,
    clust_rel_pad=0.0
):
    unique_labels = set(labels)
    density = {}

    for label in unique_labels:
        if label == -1:
            continue

        insets_per_label = np.where(labels == label)
        inset_centroids = all_inset_centroids[insets_per_label]
        inset_dims = all_inset_dims[insets_per_label]
        inset_disp_area_total = np.sum(all_inset_disp_area[insets_per_label])
        bbox = bbox_points(inset_dims)
        bbox_area = bbox[4] * bbox[5]

        mean_dist = np.mean(
            # the mean distance to oneself is always 0, so ... boring!
            np.sum(
                pairwise_distances(inset_centroids), axis=0
            ) / (inset_centroids.shape[0] - 1)
        )

        density[str(label)] = {
            'inset_stress': inset_disp_area_total / bbox_area,
            'mean_dist': 0 if math.isnan(mean_dist) else mean_dist,
            'num_insets': inset_centroids.shape[0],
        }

    return density


def cluster_points(points, method, config):
    if method == 'density':
        db = HDBSCAN(min_cluster_size=config['min_cluster_size']).fit(points)

    else:
        width = config['width']
        height = config['height']
        clust_per_max = config['clust_per_max']
        part = max(width, height) * (1 / clust_per_max)

        landscape = width > height

        num_clust_x = int(
            clust_per_max
            if landscape
            else clust_per_max - np.floor((height - width) / part)
        )
        init_x = np.linspace(0, width, num=num_clust_x + 2)[1:num_clust_x + 1]

        num_clust_y = int(
            clust_per_max
            if not landscape
            else clust_per_max - np.floor((width - height) / part)
        )
        init_y = np.linspace(0, height, num=num_clust_y + 2)[1:num_clust_y + 1]

        print(cartesian([init_x, init_y]))

        db = MiniBatchKMeans(
            n_clusters=num_clust_x * num_clust_y,
            init=cartesian([init_x, init_y]),
            n_init=1
        ).fit(points)

    # Get labels
    labels = db.labels_

    # "-1" is the cluster of noise
    num_clust = labels.max() + 1

    return (labels, num_clust)


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


def get_frag_by_loc_from_cool(
    cooler_file,
    loci,
    dim,
    zoomout_level=0,
    balanced=True,
    padding=None,
    percentile=100.0,
    ignore_diags=0,
    no_normalize=False
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
            ignore_diags=ignore_diags,
            no_normalize=no_normalize
        )

    return fragments


def get_frag_by_loc_from_imtiles(
    imtiles_file,
    loci,
    zoom_level=0,
    padding=0,
    tile_size=256
):
    db = sqlite3.connect(imtiles_file)
    info = db.execute('SELECT * FROM tileset_info').fetchone()
    max_zoom = info[6]
    max_width = info[8]
    max_height = info[9]
    im_type = 'JPEG' if info[10].lower() == 'jpg' else info[10]

    div = 2 ** (max_zoom - zoom_level)
    width = max_width / div
    height = max_height / div

    ims = []

    for locus in loci:
        start1 = round(locus[0] / div)
        end1 = round(locus[1] / div)
        start2 = round(locus[2] / div)
        end2 = round(locus[3] / div)

        if not is_within(start1, end1, start2, end2, width, height):
            ims.append(None)
            continue

        # Get tile ids
        tile_start1_id = start1 // tile_size
        tile_end1_id = end1 // tile_size
        tile_start2_id = start2 // tile_size
        tile_end2_id = end2 // tile_size

        tiles_x_range = range(tile_start1_id, tile_end1_id + 1)
        tiles_y_range = range(tile_start2_id, tile_end2_id + 1)

        # Extract image tiles
        tiles = []
        for y in tiles_y_range:
            for x in tiles_x_range:
                tiles.append(Image.open(BytesIO(db.execute(
                    'SELECT image FROM tiles WHERE z=? AND y=? AND x=?',
                    (zoom_level, y, x)
                ).fetchone()[0])))

        im = (
            tiles[0]
            if len(tiles) == 1
            else Image.new(
                'RGB',
                (
                    tile_size * len(tiles_x_range),
                    tile_size * len(tiles_y_range)
                )
            )
        )

        # Stitch them tiles together
        if len(tiles) > 1:
            i = 0
            for y in range(len(tiles_y_range)):
                for x in range(len(tiles_x_range)):
                    im.paste(
                        tiles[i], (x * tile_size, y * tile_size)
                    )
                    i += 1

        # Convert starts and ends to local tile ids
        start1_rel = start1 - tile_start1_id * tile_size
        end1_rel = end1 - tile_start1_id * tile_size
        start2_rel = start2 - tile_start2_id * tile_size
        end2_rel = end2 - tile_start2_id * tile_size

        # Cut out the corresponding snippet
        im_out = im.crop((start1_rel, start2_rel, end1_rel, end2_rel))

        im_buffer = BytesIO()
        im_out.save(im_buffer, format=im_type)
        ims.append((im_buffer.getvalue(), 'image/{}'.format(im_type.lower())))

    db.close()

    return ims


def get_frag_by_loc_from_osm(
    imtiles_file,
    loci,
    zoom_level=0,
    padding=0,
    tile_size=256
):
    width = 360
    height = 180
    im_type = 'PNG'

    ims = []

    for locus in loci:
        start_lng = locus[0]
        end_lng = locus[1]
        start_lat = locus[2]
        end_lat = locus[3]

        if not is_within(
            start_lng + 180,
            end_lng + 180,
            end_lat + 90,
            start_lat + 90,
            width,
            height
        ):
            ims.append(None)
            continue

        # Get tile ids
        start1, start2 = geotu.get_tile_pos_from_lng_lat(
            start_lng, start_lat, zoom_level
        )
        end1, end2 = geotu.get_tile_pos_from_lng_lat(
            end_lng, end_lat, zoom_level
        )

        xPad = padding * (end1 - start1)
        yPad = padding * (start2 - end2)

        start1 -= xPad
        end1 += xPad
        start2 += yPad
        end2 -= yPad

        tile_start1_id = math.floor(start1)
        tile_start2_id = math.floor(start2)
        tile_end1_id = math.floor(end1)
        tile_end2_id = math.floor(end2)

        start1 = math.floor(start1 * tile_size)
        start2 = math.floor(start2 * tile_size)
        end1 = math.ceil(end1 * tile_size)
        end2 = math.ceil(end2 * tile_size)

        tiles_x_range = range(tile_start1_id, tile_end1_id + 1)
        tiles_y_range = range(tile_start2_id, tile_end2_id + 1)

        # Extract image tiles
        tiles = []
        for y in tiles_y_range:
            for x in tiles_x_range:
                prefixes = ['a', 'b', 'c']
                prefix_idx = math.floor(random() * len(prefixes))
                src = (
                    'http://{}.tile.openstreetmap.org/{}/{}/{}.png'
                    .format(prefixes[prefix_idx], zoom_level, x, y)
                )

                r = requests.get(src)
                if r.status_code == 200:
                    tiles.append(Image.open(BytesIO(r.content)))
                else:
                    tiles.append(None)

        im = (
            tiles[0]
            if len(tiles) == 1
            else Image.new(
                'RGB',
                (
                    tile_size * len(tiles_x_range),
                    tile_size * len(tiles_y_range)
                )
            )
        )

        # Stitch them tiles together
        if len(tiles) > 1:
            i = 0
            for y in range(len(tiles_y_range)):
                for x in range(len(tiles_x_range)):
                    im.paste(
                        tiles[i], (x * tile_size, y * tile_size)
                    )
                    i += 1

        # Convert starts and ends to local tile ids
        start1_rel = start1 - tile_start1_id * tile_size
        end1_rel = end1 - tile_start1_id * tile_size
        start2_rel = start2 - tile_start2_id * tile_size
        end2_rel = end2 - tile_start2_id * tile_size

        # Cut out the corresponding snippet
        im_out = im.crop((start1_rel, start2_rel, end1_rel, end2_rel))

        im_buffer = BytesIO()
        im_out.save(im_buffer, format=im_type)
        ims.append((im_buffer.getvalue(), 'image/{}'.format(im_type.lower())))

    return ims


def is_within(start1, end1, start2, end2, width, height):
    return start1 < width and end1 > 0 and start2 < height and end2 > 0


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
    ignore_diags=0,
    no_normalize=False
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
            ignore_diags=ignore_diags,
            no_normalize=no_normalize
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
    ignore_diags: int = 0,
    no_normalize: bool = False
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
        no_normalize:
            If `true` the returned matrix is not normalized.
            Defaults to `False`.

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

    # Finally, adjust to negative values.
    # Since relative bin IDs are adjusted by the start this will lead to a
    # white offset.
    real_start_bin1 = start_bin1 if start_bin1 >= 0 else 0
    real_start_bin2 = start_bin2 if start_bin2 >= 0 else 0

    # Get the data
    data = c.matrix(
        as_pixels=True, balance=False, max_chunk=np.inf
    )[real_start_bin1:end_bin1, real_start_bin2:end_bin2]

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
    diags_start_row = None
    if ignore_diags > 0:
        try:
            diags_start_idx = np.min(
                np.where(data['bin1_id'].values == data['bin2_id'].values)
            )
            diags_start_row = (
                rel_bin1[diags_start_idx] - rel_bin2[diags_start_idx]
            )
        except ValueError:
            pass

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
    if not no_normalize:
        min_val = np.min(frag)
        frag -= min_val

    # Remove diagonals
    if ignore_diags > 0 and diags_start_row is not None:
        if width == height:
            scaled_row = int(np.rint(diags_start_row / scale_x))

            idx = np.diag_indices(width)
            scaled_idx = (
                idx
                if scaled_row == 0
                else [idx[0][scaled_row:], idx[0][:-scaled_row]]
            )

            for i in range(ignore_diags):

                if i == 0:
                    frag[scaled_idx] = 0
                else:
                    dist_to_diag = scaled_row - i
                    dist_neg = min(0, dist_to_diag)
                    off = 0 if dist_to_diag >= 0 else i - scaled_row

                    # Above diagonal
                    frag[
                        ((scaled_idx[0] - i)[off:], (scaled_idx[1])[off:])
                    ] = 0

                    # Extra cutoff at the bottom right
                    frag[
                        (
                            range(
                                scaled_idx[0][-1] - i,
                                scaled_idx[0][-1] + 1 + dist_neg,
                            ),
                            range(
                                scaled_idx[1][-1],
                                scaled_idx[1][-1] + i + 1 + dist_neg
                            )
                        )
                    ] = 0

                    # Below diagonal
                    frag[
                        ((scaled_idx[0] + i)[:-i], (scaled_idx[1])[:-i])
                    ] = 0
        else:
            logger.warn(
                'Ignoring the diagonal only supported for squared features'
            )

    # Capp by percentile
    max_val = np.percentile(frag, percentile)
    frag = np.clip(frag, 0, max_val)

    # Normalize by maximum
    if not no_normalize and max_val > 0:
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
