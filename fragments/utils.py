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

from random import random
from io import BytesIO, StringIO
from PIL import Image
from sklearn.cluster import KMeans
from scipy.ndimage.interpolation import zoom
from cachecontrol import CacheControl
from zipfile import ZipFile

from django.http import HttpResponse

from clodius.tiles.geo import get_tile_pos_from_lng_lat

import higlass_server.settings as hss

from higlass_server.utils import getRdb
from fragments.exceptions import SnippetTooLarge

import zlib
import struct

rdb = getRdb()

logger = logging.getLogger(__name__)


# Methods

def grey_to_rgb(arr, to_rgba=False):
    if to_rgba:
        rgb = np.zeros(arr.shape + (4,))
        rgb[:, :, 3] = 255
    else:
        rgb = np.zeros(arr.shape + (3,))

    rgb[:, :, 0] = 255 - arr * 255
    rgb[:, :, 1] = rgb[:,:,0]
    rgb[:, :, 2] = rgb[:,:,0]

    return rgb


def blob_to_zip(blobs, to_resp=False):
    b = BytesIO()

    zf = ZipFile(b, 'w')

    for blob in blobs:
        zf.writestr(blob['name'], blob['bytes'])

    zf.close()

    if to_resp:
        resp = HttpResponse(b.getvalue(), content_type='application/zip')
        resp['Content-Disposition'] = 'attachment; filename=snippets.zip'

        return resp

    return b.getvalue()


def np_to_png(arr, comp=5):
    sz = arr.shape

    # Add alpha values
    if arr.shape[2] == 3:
        out = np.ones(
            (sz[0], sz[1], sz[2] + 1)
        )
        out[:, :, 3] = 255
        out[:, :, 0:3] = arr
    else:
        out = arr

    return write_png(
        np.flipud(out).astype('uint8').flatten('C').tobytes(),
        sz[1],
        sz[0],
        comp
    )


def png_pack(png_tag, data):
    chunk_head = png_tag + data
    return (struct.pack("!I", len(data)) +
            chunk_head +
            struct.pack("!I", 0xFFFFFFFF & zlib.crc32(chunk_head)))


def write_png(buf, width, height, comp=9):
    """ buf: must be bytes or a bytearray in Python3.x,
        a regular string in Python2.x.
    """

    # reverse the vertical line order and add null bytes at the start
    width_byte_4 = width * 4
    raw_data = b''.join(
        b'\x00' + buf[span:span + width_byte_4]
        for span in np.arange((height - 1) * width_byte_4, -1, - width_byte_4)
    )

    return b''.join([
        b'\x89PNG\r\n\x1a\n',
        png_pack(b'IHDR', struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)),
        png_pack(b'IDAT', zlib.compress(raw_data, comp)),
        png_pack(b'IEND', b'')])


def get_params(request, param_def):
    """Get query params of a request

    Retrieve query params of a request given the parameter definition file. A
    parameter definition looks like
    ```
    '<PARAMETER FULL NAME>': {
        'short': '<PARAMETER SHORT NAME>',
        'dtype': '<PARAMETER DATA TYPE>',
        'help': '<PARAMETER HELP MESSAGE>'
    }
    ```

    Arguments:
        request {request} -- Request object
        param_def {dict} -- [description]

    Returns:
        dict -- Dictionary of parameter name<>values pairs
    """
    p = {}
    dtype = {
        'int': int,
        'float': float,
        'bool': bool,
        'str': str,
    }

    for key in param_def.keys():

        p[key] = request.GET.get(param_def[key]['short'])
        p[key] = p[key] if p[key] else request.GET.get(key)
        p[key] = p[key] if p[key] else param_def[key]['default']
        p[key] = dtype[param_def[key]['dtype']](p[key])

    return p


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


def get_cooler(f, zoomout_level=None):
    c = None

    try:
        # Cooler v2
        # In this case `zoomout_level` is the resolution
        # See fragments/views.py line 431

        resolutions = [int(x) for x in f['resolutions'].keys()]
        resolution = min(resolutions) if zoomout_level is None else zoomout_level

        # Get the closest zoomlevel
        resolution = resolutions[np.argsort([abs(r - resolution) for r in resolutions])[0]]

        return cooler.Cooler(f['resolutions/{}'.format(resolution)])
    except:
        # We're not logging this exception as the user might just try to open
        # a cooler v1 file
        pass


    try:
        # v1
        zoomout_level = 0 if zoomout_level is None else zoomout_level
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
        logger.exception(e)

    try:
        c = cooler.Cooler(f)
    except Exception as e:
        logger.exception(e)

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
    no_normalize=False,
    aggregate=False,
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
            no_normalize=no_normalize,
            aggregate=aggregate
        )

    return fragments


def get_scale_frags_to_same_size(frags, loci_ids, out_size=-1, no_cache=False):
    """Scale fragments to same size

    [description]

    Arguments:
        frags {list} -- List of numpy arrays representing the fragments

    Returns:
        np.array -- Numpy array of scaled fragments
    """
    # Use the smallest dim
    dim_x = np.inf
    dim_y = np.inf
    is_image = False

    largest_frag_idx = -1
    largest_frag_size = 0
    smallest_frag_idx = -1
    smallest_frag_size = np.inf

    for i, frag in enumerate(frags):
        is_image = is_image or frag.ndim == 3

        if is_image:
            f_dim_y, f_dim_x, _ = frag.shape  # from PIL.Image
        else:
            f_dim_x, f_dim_y = frag.shape

        size = f_dim_x * f_dim_y

        if size > largest_frag_size:
            largest_frag_idx = i
            largest_frag_size = size

        if size < smallest_frag_size:
            smallest_frag_idx = i
            smallest_frag_size = size

        dim_x = min(dim_x, f_dim_x)
        dim_y = min(dim_y, f_dim_y)

    if out_size != -1 and not no_cache:
        dim_x = out_size
        dim_y = out_size

    if is_image:
        out = np.zeros([len(frags), dim_y, dim_x, 3])
    else:
        out = np.zeros([len(frags), dim_x, dim_y])

    for i, frag in enumerate(frags):
        id = loci_ids[i] + '.' + '.'.join(map(str, out.shape[1:]))

        if not no_cache:
            frag_ds = None
            try:
                frag_ds = np.load(BytesIO(rdb.get('im_snip_ds_%s' % id)))
                if frag_ds is not None:
                    out[i] = frag_ds
                    continue
            except:
                pass

        if is_image:
            f_dim_y, f_dim_x, _ = frag.shape  # from PIL.Image
            scaledFrag = np.zeros((dim_y, dim_x, 3), float)
        else:
            f_dim_x, f_dim_y = frag.shape
            scaledFrag = np.zeros((dim_x, dim_y), float)

        # Downsample
        # if f_dim_x > dim_x or f_dim_y > dim_y:

        # stupid zoom doesn't accept the final shape. Carefully crafting
        # the multipliers to make sure that it will work.
        zoomMultipliers = np.array(scaledFrag.shape) / np.array(frag.shape)
        frag = zoom(frag, zoomMultipliers, order=1)

        # frag = scaledFrag + zoomArray(frag,
        #     frag, scaledFrag.shape, order=1
        # )

        if not no_cache:
            with BytesIO() as b:
                np.save(b, frag)
                rdb.set('im_snip_ds_%s' % id, b.getvalue(), 60 * 30)

        out[i] = frag

    return out, largest_frag_idx, smallest_frag_idx


def get_rep_frags(frags, loci, loci_ids, num_reps=4, no_cache=False):
    """Get a number of representatives for each cluster

    [description]

    Arguments:
        frags {list} -- List of numpy arrays representing the fragment
        num_reps {int} -- Number of representatives
    """
    num_frags = len(frags)

    if num_frags < 5:
        sizes = np.zeros([num_frags])

        for i, frag in enumerate(frags):
            sizes[i] = np.prod(frag.shape[0:2])

        idx = np.argsort(sizes).astype(np.uint8)[::-1]

        return [frags[i] for i in idx], idx

    out, _, _ = get_scale_frags_to_same_size(
        frags, loci_ids, 32, no_cache
    )

    # Get largest frag based on world coords
    largest_a = 0
    for i, locus in enumerate(loci):
        a = abs(locus[1] - locus[0]) * abs(locus[3] - locus[2])
        if a > largest_a:
            largest_a = a
            largest_frag_idx = i

    mean_frag = np.nanmean(out, axis=0)
    diff_mean_frags = out - mean_frag

    # Sum each x,y and c (channel) value up per f (fragment) and take the
    # sqaure root to get the L2 norm
    dist_to_mean = np.sqrt(
        np.einsum('fxyc,fxyc->f', diff_mean_frags, diff_mean_frags)
    )

    # Get the fragment closest to the mean
    # Get the index of the i-th smallest value i=0 == smallest value
    closest_mean_frag_idx = np.argpartition(dist_to_mean, 0)[0]
    if closest_mean_frag_idx == largest_frag_idx:
        closest_mean_frag_idx = np.argpartition(dist_to_mean, 1)[1]

    # Get the frag farthest away from
    for i in range(len(dist_to_mean) - 1, -1, -1):
        farthest_mean_frag_idx = np.argpartition(dist_to_mean, i)[i]
        if (
            farthest_mean_frag_idx != largest_frag_idx and
            farthest_mean_frag_idx != closest_mean_frag_idx
        ):
            break

    # Distance to farthest away frag
    diff_farthest_frags = out - out[np.argmax(dist_to_mean)]
    dist_to_farthest = np.sqrt(
        np.einsum('fxyc,fxyc->f', diff_farthest_frags, diff_farthest_frags)
    )

    # Get the frag farthest away from the frag farthest away from the mean
    for i in range(len(dist_to_farthest) - 1, -1, -1):
        farthest_farthest_frag_idx = np.argpartition(dist_to_farthest, i)[i]
        if (
            farthest_farthest_frag_idx != largest_frag_idx and
            farthest_farthest_frag_idx != closest_mean_frag_idx and
            farthest_farthest_frag_idx != farthest_mean_frag_idx
        ):
            break

    frags = [
        frags[largest_frag_idx],
        frags[closest_mean_frag_idx],
        frags[farthest_mean_frag_idx],
        frags[farthest_farthest_frag_idx]
    ]

    idx = [
        largest_frag_idx,
        closest_mean_frag_idx,
        farthest_mean_frag_idx,
        farthest_farthest_frag_idx
    ]

    return frags, idx


def aggregate_frags(
    frags,
    loci_ids,
    method='mean',
    max_previews=8,
):
    """Aggregate multiple fragments into one

    Arguments:
        frags {list} -- A list of numpy arrays to be aggregated

    Keyword Arguments:
        method {str} -- Aggregation method. Available methods are
            {'mean', 'median', 'std', 'var'}. (default: {'mean'})

    Returns:
        np.array -- Numpy array aggregated by the fragments. This array
            represents the image aggregation.
        np.array -- Numpy arrat aggregated along the Y axis. This array
            represents the 1D previews.
    """
    out, _, _ = get_scale_frags_to_same_size(frags, loci_ids, -1, True)

    if max_previews > 0:
        if len(frags) > max_previews:
            clusters = KMeans(n_clusters=max_previews, random_state=0).fit(
                np.reshape(out, (out.shape[0], -1))
            )
            previews = np.zeros((max_previews,) + out.shape[2:])

        else:
            previews = np.zeros((len(frags),) + out.shape[2:])

    previews_2d = []

    if method == 'median':
        aggregate = np.nanmedian(out, axis=0)
        if len(frags) > max_previews:
            for i in range(max_previews):
                previews[i] = np.nanmedian(
                    out[np.where(clusters.labels_ == i)], axis=1
                )[0]
        else:
            previews = np.nanmedian(out, axis=1)
        return aggregate, previews

    elif method == 'std':
        aggregate = np.nanstd(out, axis=0)
        if len(frags) > max_previews:
            for i in range(max_previews):
                previews[i] = np.nanstd(
                    out[np.where(clusters.labels_ == i)], axis=1
                )[0]
        else:
            previews = np.nanmedian(out, axis=1)
        return aggregate, previews

    elif method == 'var':
        aggregate = np.nanvar(out, axis=0)
        if len(frags) > max_previews:
            for i in range(max_previews):
                previews[i] = np.nanvar(
                    out[np.where(clusters.labels_ == i)], axis=1
                )[0]
        else:
            previews = np.nanmedian(out, axis=1)
        return aggregate, previews

    elif method != 'mean':
        print('Unknown aggregation method: {}'.format(method))

    aggregate = np.nanmean(out, axis=0)
    if max_previews > 0:
        if len(frags) > max_previews:
            for i in range(max_previews):
                # Aggregated preview
                previews[i] = np.nanmean(
                    out[np.where(clusters.labels_ == i)[0]], axis=1
                )[0]
                previews_2d.append(np.nanmean(
                    out[np.where(clusters.labels_ == i)], axis=0
                ))
        else:
            previews = np.nanmedian(out, axis=1)
            previews_2d = frags
    else:
        previews = None
        previews_2d = None

    return aggregate, previews, previews_2d


def get_frag_from_image_tiles(
    tiles,
    tile_size,
    tiles_x_range,
    tiles_y_range,
    tile_start1_id,
    tile_start2_id,
    from_x,
    to_x,
    from_y,
    to_y
):
    im = (
        tiles[0]
        if len(tiles) == 1
        else Image.new(
            'RGB',
            (tile_size * len(tiles_x_range), tile_size * len(tiles_y_range))
        )
    )

    # Stitch them tiles together
    if len(tiles) > 1:
        i = 0
        for y in range(len(tiles_y_range)):
            for x in range(len(tiles_x_range)):
                im.paste(tiles[i], (x * tile_size, y * tile_size))
                i += 1

    # Convert starts and ends to local tile ids
    start1_rel = from_x - tile_start1_id * tile_size
    end1_rel = to_x - tile_start1_id * tile_size
    start2_rel = from_y - tile_start2_id * tile_size
    end2_rel = to_y - tile_start2_id * tile_size

    # Notice the shape: height x width x channel
    return np.array(im.crop((start1_rel, start2_rel, end1_rel, end2_rel)))


def get_frag_by_loc_from_imtiles(
    imtiles_file,
    loci,
    zoom_level=0,
    padding=0,
    tile_size=256,
    no_cache=False
):
    db = None
    div = 1
    width = 0
    height = 0

    ims = []

    got_info = False

    for locus in loci:
        id = locus[-1]

        if not no_cache:
            im_snip = None
            try:
                im_snip = np.load(BytesIO(rdb.get('im_snip_%s' % id)))
                if im_snip is not None:
                    ims.append(im_snip)
                    continue
            except:
                pass

        if not got_info:
            db = sqlite3.connect(imtiles_file)
            info = db.execute('SELECT * FROM tileset_info').fetchone()

            max_zoom = info[6]
            max_width = info[8]
            max_height = info[9]

            div = 2 ** (max_zoom - zoom_level)
            width = max_width / div
            height = max_height / div

            got_info = True

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

        # Make sure that no more than 6 standard tiles (256px) are loaded.
        if tile_size * len(tiles_x_range) > hss.SNIPPET_IMT_MAX_DATA_DIM:
            raise SnippetTooLarge()
        if tile_size * len(tiles_y_range) > hss.SNIPPET_IMT_MAX_DATA_DIM:
            raise SnippetTooLarge()

        # Extract image tiles
        tiles = []
        for y in tiles_y_range:
            for x in tiles_x_range:
                tiles.append(Image.open(BytesIO(db.execute(
                    'SELECT image FROM tiles WHERE z=? AND y=? AND x=?',
                    (zoom_level, y, x)
                ).fetchone()[0])))

        im_snip = get_frag_from_image_tiles(
            tiles,
            tile_size,
            tiles_x_range,
            tiles_y_range,
            tile_start1_id,
            tile_start2_id,
            start1,
            end1,
            start2,
            end2
        )

        # Cache for 30 min
        if not no_cache:
            with BytesIO() as b:
                np.save(b, im_snip)
                rdb.set('im_snip_%s' % id, b.getvalue(), 60 * 30)

        ims.append(im_snip)

    if db:
        db.close()

    return ims


def get_frag_by_loc_from_osm(
    imtiles_file,
    loci,
    zoom_level=0,
    padding=0,
    tile_size=256,
    no_cache=False
):
    width = 360
    height = 180

    ims = []

    prefixes = ['a', 'b', 'c']
    prefix_idx = math.floor(random() * len(prefixes))
    osm_src = 'http://{}.tile.openstreetmap.org'.format(prefixes[prefix_idx])

    s = CacheControl(requests.Session())

    for locus in loci:
        id = locus[-1]

        if not no_cache:
            osm_snip = None
            try:
                osm_snip = np.load(BytesIO(rdb.get('osm_snip_%s' % id)))
                if osm_snip is not None:
                    ims.append(osm_snip)
                    continue
            except:
                pass

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
        start1, start2 = get_tile_pos_from_lng_lat(
            start_lng, start_lat, zoom_level
        )
        end1, end2 = get_tile_pos_from_lng_lat(
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

        # Make sure that no more than 6 standard tiles (256px) are loaded.
        if tile_size * len(tiles_x_range) > hss.SNIPPET_OSM_MAX_DATA_DIM:
            raise SnippetTooLarge()
        if tile_size * len(tiles_y_range) > hss.SNIPPET_OSM_MAX_DATA_DIM:
            raise SnippetTooLarge()

        # Extract image tiles
        tiles = []
        for y in tiles_y_range:
            for x in tiles_x_range:
                src = (
                    '{}/{}/{}/{}.png'
                    .format(osm_src, zoom_level, x, y)
                )

                r = s.get(src)

                if r.status_code == 200:
                    tiles.append(Image.open(
                        BytesIO(r.content)
                    ).convert('RGB'))
                else:
                    tiles.append(None)

        osm_snip = get_frag_from_image_tiles(
            tiles,
            tile_size,
            tiles_x_range,
            tiles_y_range,
            tile_start1_id,
            tile_start2_id,
            start1,
            end1,
            start2,
            end2
        )

        if not no_cache:
            with BytesIO() as b:
                np.save(b, osm_snip)
                rdb.set('osm_snip_%s' % id, b.getvalue(), 60 * 30)

        ims.append(osm_snip)

    return ims


def is_within(start1, end1, start2, end2, width, height):
    return start1 < width and end1 > 0 and start2 < height and end2 > 0


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
    ignore_diags=0,
    no_normalize=False,
    aggregate=False
):
    fragments = []

    for locus in loci:
        last_loc = len(locus) - 2
        fragments.append(get_frag(
            c,
            resolution,
            offsets,
            *locus[:6],
            width=locus[last_loc] if locus[last_loc] else dim,
            padding=padding,
            balanced=balanced,
            percentile=percentile,
            ignore_diags=ignore_diags,
            no_normalize=no_normalize
        ))

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

    try:
        offset1 = offsets[chrom1]
    except KeyError:
        # One more try before we will fail miserably
        offset1 = offsets['chr{}'.format(chrom1)]

    try:
        offset2 = offsets[chrom2]
    except KeyError:
        # One more try before we will fail miserably
        offset2 = offsets['chr{}'.format(chrom2)]

    start_bin1 = offset1 + int(round(float(start1) / resolution))
    end_bin1 = offset1 + int(round(float(end1) / resolution)) + 1

    start_bin2 = offset2 + int(round(float(start2) / resolution))
    end_bin2 = offset2 + int(round(float(end2) / resolution)) + 1

    # Apply percentile padding
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

    # In case the final dimension does not math the desired dimension we
    # increase the end bin. This can be caused when the padding is not
    # divisible by 2, since the padding is rounded to the nearest integer.
    abs_dim1 = abs(start_bin1 - end_bin1)
    if abs_dim1 < width:
        end_bin1 += width - abs_dim1
        abs_dim1 = width

    abs_dim2 = abs(start_bin2 - end_bin2)
    if abs_dim2 < height:
        end_bin2 += height - abs_dim2
        abs_dim2 = height

    # Maximum width / height is 512
    if abs_dim1 > hss.SNIPPET_MAT_MAX_DATA_DIM: raise SnippetTooLarge()
    if abs_dim2 > hss.SNIPPET_MAT_MAX_DATA_DIM: raise SnippetTooLarge()

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
    frag_len = abs_dim1 * abs_dim2
    frag = np.zeros(frag_len, dtype=np.float32)
    # Make sure we're within the bounds
    idx1_f = np.where(idx1 < frag_len)
    frag[idx1[idx1_f]] = values[idx1_f]
    frag[idx2[validBins]] = values[validBins]
    frag = frag.reshape((abs_dim1, abs_dim2))

    # Store low quality bins
    low_quality_bins = np.where(np.isnan(frag))

    # Assign 0 for now to avoid influencing the max values
    frag[low_quality_bins] = 0

    # Scale fragment down if needed
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

    ignored_idx = None

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

                # First set all cells to be ignored to `-1` so that we can
                # easily query for them later.
                if i == 0:
                    frag[scaled_idx] = -1
                else:
                    dist_to_diag = scaled_row - i
                    dist_neg = min(0, dist_to_diag)
                    off = 0 if dist_to_diag >= 0 else i - scaled_row

                    # Above diagonal
                    frag[
                        ((scaled_idx[0] - i)[off:], (scaled_idx[1])[off:])
                    ] = -1

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
                    ] = -1

                    # Below diagonal
                    frag[
                        ((scaled_idx[0] + i)[:-i], (scaled_idx[1])[:-i])
                    ] = -1

            # Save the final selection of ignored cells for fast access
            # later and set those values to `0` now.
            ignored_idx = np.where(frag == -1)
            frag[ignored_idx] = 0

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

    # Set the ignored diagonal to the maximum
    if ignored_idx:
        frag[ignored_idx] = 1.0

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
