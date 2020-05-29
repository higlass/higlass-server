import base64
#import tilesets.bigwig_tiles as bwt
import clodius.db_tiles as cdt
import clodius.hdf_tiles as hdft
import collections as col

import clodius.tiles.bam as ctb
import clodius.tiles.beddb as hgbe
import clodius.tiles.bigwig as hgbi
import clodius.tiles.bigbed as hgbb
import clodius.tiles.cooler as hgco
import clodius.tiles.geo as hggo
import clodius.tiles.imtiles as hgim

import h5py
import itertools as it
import numpy as np
import os
import shutil
import time
import tempfile
import tilesets.models as tm
import tilesets.chromsizes  as tcs

import higlass.tilesets as hgti

import clodius.tiles.multivec as ctmu

import higlass_server.settings as hss

def get_tileset_datatype(tileset):
    '''
    Extract the filetype for the tileset

    This should be encoded in one of the tags. If there are multiple
    "datatype" tags, use the most recent one.
    '''
    if tileset.datatype is not None and len(tileset.datatype) > 0:
        return tileset.datatype

    for tag in tileset.tags.all():
        parts = tag.name.split(':')
        if parts[0] == 'datatype':
            return parts[1]

    # fall back to the filetype attribute of the tileset
    return tileset.datatype

def get_cached_datapath(path):
    '''
    Check if we need to cache this file or if we have a cached copy

    Parameters
    ----------
    filename: str
        The original filename

    Returns
    -------
    filename: str
        Either the cached filename if we're caching or the original
        filename
    '''
    if hss.CACHE_DIR is None:
        # no caching requested
        return path

    orig_path = path
    cached_path = op.join(hss.CACHE_DIR, path)

    if op.exists(cached_path):
        # this file has already been cached
        return cached_path

    with tempfile.TemporaryDirectory() as dirpath:
        tmp = op.join(dirpath, 'cached_file')
        shutil.copyfile(orig_path, tmp)

        # check to make sure the destination directory exists
        dest_dir = op.dirname(cached_path)

        if not op.exists(dest_dir):
            os.makedirs(dest_dir)

        shutil.move(tmp, cached_path)

    return cached_path

def extract_tileset_uid(tile_id):
    '''
    Get the tileset uid from a tile id. Should usually be all the text
    before the first dot.

    Parameters
    ----------
    tile_id : str
        The id of the tile we're getting the tileset info for (e.g. xyz.0.0.1)
    Returns
    -------
    tileset_uid : str
        The uid of the tileset that this tile comes from
    '''
    tile_id_parts = tile_id.split('.')
    tileset_uuid = tile_id_parts[0]

    return tileset_uuid


def get_tileset_filetype(tileset):
    return tileset.filetype

def generate_1d_tiles(filename, tile_ids, get_data_function, tileset_options):
    '''
    Generate a set of tiles for the given tile_ids.

    Parameters
    ----------
    filename: str
        The file containing the multiresolution data
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0) identifying the tiles
        to be retrieved
    get_data_function: lambda
        A function which retrieves the data for this tile
    tileset_options: dict or None
        An optional dict containing options, including aggregation options.

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''

    agg_func_map = {
        "sum": lambda x: np.sum(x, axis=0),
        "mean": lambda x: np.mean(x, axis=0),
        "median": lambda x: np.median(x, axis=0),
        "std": lambda x: np.std(x, axis=0),
        "var": lambda x: np.var(x, axis=0),
        "max": lambda x: np.amax(x, axis=0),
        "min": lambda x: np.amin(x, axis=0),
    }

    generated_tiles = []

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:3]))

        dense = get_data_function(filename, tile_position)

        if tileset_options != None and "aggGroups" in tileset_options and "aggFunc" in tileset_options:
            agg_func_name = tileset_options["aggFunc"]
            agg_group_arr = [ x if type(x) == list else [x] for x in tileset_options["aggGroups"] ]
            dense = np.array(list(map(agg_func_map[agg_func_name], [ dense[arr] for arr in agg_group_arr ])))
        
        if len(dense):
            max_dense = max(dense.reshape(-1,))
            min_dense = min(dense.reshape(-1,))
        else:
            max_dense = 0
            min_dense = 0

        min_f16 = np.finfo('float16').min
        max_f16 = np.finfo('float16').max

        has_nan = len([d for d in dense.reshape((-1,)) if np.isnan(d)]) > 0

        if (
            not has_nan and
            max_dense > min_f16 and max_dense < max_f16 and
            min_dense > min_f16 and min_dense < max_f16
        ):
            tile_value = {
                'dense': base64.b64encode(dense.reshape((-1,)).astype('float16')).decode('utf-8'),
                'dtype': 'float16',
                'shape': dense.shape
            }
        else:
            tile_value = {
                'dense': base64.b64encode(dense.reshape((-1,)).astype('float32')).decode('utf-8'),
                'dtype': 'float32',
                'shape': dense.shape
            }

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def get_chromsizes(tileset):
    '''
    Get a set of chromsizes matching the coordSystem of this
    tileset.

    Parameters
    ----------
    tileset: A tileset DJango model object

    Returns
    -------
    chromsizes: [[chrom, sizes]]
        A set of chromsizes to be used with this bigWig file.
        None if no chromsizes tileset with this coordSystem
        exists or if two exist with this coordSystem.
    '''
    if tileset.coordSystem is None or len(tileset.coordSystem) == None:
        return None

    try:
        chrom_info_tileset = tm.Tileset.objects.get(coordSystem=tileset.coordSystem,
                datatype='chromsizes')
    except:
        return None

    return tcs.get_tsv_chromsizes(chrom_info_tileset.datafile.path)

def generate_hitile_tiles(tileset, tile_ids):
    '''
    Generate tiles from a hitile file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:3]))

        dense = hdft.get_data(
            h5py.File(
                tileset.datafile.path
            ),
            tile_position[0],
            tile_position[1]
        )

        if len(dense):
            max_dense = max(dense)
            min_dense = min(dense)
        else:
            max_dense = 0
            min_dense = 0

        min_f16 = np.finfo('float16').min
        max_f16 = np.finfo('float16').max

        has_nan = len([d for d in dense if np.isnan(d)]) > 0

        if (
            not has_nan and
            max_dense > min_f16 and max_dense < max_f16 and
            min_dense > min_f16 and min_dense < max_f16
        ):
            tile_value = {
                'dense': base64.b64encode(dense.astype('float16')).decode('utf-8'),
                'dtype': 'float16'
            }
        else:
            tile_value = {
                'dense': base64.b64encode(dense.astype('float32')).decode('utf-8'),
                'dtype': 'float32'
            }

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def generate_bed2ddb_tiles(tileset, tile_ids, retriever=cdt.get_2d_tiles):
    '''
    Generate tiles from a bed2db file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []

    tile_ids_by_zoom = bin_tiles_by_zoom(tile_ids).values()
    partitioned_tile_ids = list(it.chain(*[partition_by_adjacent_tiles(t)
        for t in tile_ids_by_zoom]))

    for tile_group in partitioned_tile_ids:
        zoom_level = int(tile_group[0].split('.')[1])
        tileset_id = tile_group[0].split('.')[0]

        tile_positions = [[int(x) for x in t.split('.')[2:4]] for t in tile_group]

        # filter for tiles that are in bounds for this zoom level
        tile_positions = list(filter(lambda x: x[0] < 2 ** zoom_level, tile_positions))
        tile_positions = list(filter(lambda x: x[1] < 2 ** zoom_level, tile_positions))

        if len(tile_positions) == 0:
            # no in bounds tiles
            continue

        minx = min([t[0] for t in tile_positions])
        maxx = max([t[0] for t in tile_positions])

        miny = min([t[1] for t in tile_positions])
        maxy = max([t[1] for t in tile_positions])

        cached_datapath = get_cached_datapath(tileset.datafile.path)
        tile_data_by_position = retriever(
                cached_datapath,
                zoom_level,
                minx, miny,
                maxx - minx + 1,
                maxy - miny + 1
            )

        tiles = [(".".join(map(str, [tileset_id] + [zoom_level] + list(position))), tile_data)
                for (position, tile_data) in tile_data_by_position.items()]

        generated_tiles += tiles

    return generated_tiles

def generate_hibed_tiles(tileset, tile_ids):
    '''
    Generate tiles from a hibed file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []
    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:3]))
        dense = hdft.get_discrete_data(
            h5py.File(
                tileset.datafile.path
            ),
            tile_position[0],
            tile_position[1]
        )

        tile_value = {'discrete': list([list([x.decode('utf-8') for x in d]) for d in dense])}

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def bin_tiles_by_zoom(tile_ids):
    '''
    Place these tiles into separate lists according to their
    zoom level.

    Parameters
    ----------
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_lists: {zoomLevel: [tile_id, tile_id]}
        A dictionary of tile lists
    '''
    tile_id_lists = col.defaultdict(set)

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:4]))
        zoom_level = tile_position[0]

        tile_id_lists[zoom_level].add(tile_id)

    return tile_id_lists


def bin_tiles_by_zoom_level_and_transform(tile_ids):
    '''
    Place these tiles into separate lists according to their
    zoom level and transform type

    Parameters
    ----------
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_lists: {(zoomLevel, transformType): [tile_id, tile_id]}
        A dictionary of tile ids
    '''
    tile_id_lists = col.defaultdict(set)

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:4]))
        zoom_level = tile_position[0]

        transform_method = hgco.get_transform_type(tile_id)

        tile_id_lists[(zoom_level, transform_method)].add(tile_id)

    return tile_id_lists

def partition_by_adjacent_tiles(tile_ids, dimension=2):
    '''
    Partition a set of tile ids into sets of adjacent tiles

    Parameters
    ----------
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved
    dimension: int
        The dimensionality of the tiles

    Returns
    -------
    tile_lists: [tile_ids, tile_ids]
        A list of tile lists, all of which have tiles that
        are within 1 position of another tile in the list
    '''
    tile_id_lists = []

    for tile_id in sorted(tile_ids, key=lambda x: [int(p) for p in x.split('.')[2:2+dimension]]):
        tile_id_parts = tile_id.split('.')

        # exclude the zoom level in the position
        # because the tiles should already have been partitioned
        # by zoom level
        tile_position = list(map(int, tile_id_parts[2:4]))

        added = False

        for tile_id_list in tile_id_lists:
            # iterate over each group of adjacent tiles
            has_close_tile = False

            for ct_tile_id in tile_id_list:
                ct_tile_id_parts = ct_tile_id.split('.')
                ct_tile_position = list(map(int, ct_tile_id_parts[2:2+dimension]))
                far_apart = False

                # iterate over each dimension and see if this tile is close
                for p1,p2 in zip(tile_position, ct_tile_position):
                    if abs(int(p1) - int(p2)) > 1:
                        # too far apart can't be part of the same group
                        far_apart = True

                if not far_apart:
                    # no position was too far
                    tile_id_list += [tile_id]
                    added = True
                    break

            if added:
                break
        if not added:
            tile_id_lists += [[tile_id]]

    return tile_id_lists

def generate_tiles(tileset_tile_ids):
    '''
    Generate a tiles for the give tile_ids.

    All of the tile_ids must come from the same tileset. This function
    will determine the appropriate handler this tile given the tileset's
    filetype and datatype

    Parameters
    ----------
    tileset_tile_ids: tuple
        A four-tuple containing the following parameters.
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved
    raw: str or False
        The value of the GET request parameter `raw`.
    tileset_options: dict or None
        An optional dict containing tileset options, including aggregation options.

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    tileset, tile_ids, raw, tileset_options = tileset_tile_ids

    if tileset.filetype == 'hitile':
        return generate_hitile_tiles(tileset, tile_ids)
    elif tileset.filetype == 'beddb':
        return hgbe.tiles(tileset.datafile.path, tile_ids)
    elif tileset.filetype == 'bed2ddb' or tileset.filetype == '2dannodb':
        return generate_bed2ddb_tiles(tileset, tile_ids)
    elif tileset.filetype == 'geodb':
        return generate_bed2ddb_tiles(tileset, tile_ids, hggo.get_tiles)
    elif tileset.filetype == 'hibed':
        return generate_hibed_tiles(tileset, tile_ids)
    elif tileset.filetype == 'cooler':
        return hgco.generate_tiles(tileset.datafile.path, tile_ids)
    elif tileset.filetype == 'bigwig':
        chromsizes = get_chromsizes(tileset)
        return hgbi.tiles(tileset.datafile.path, tile_ids, chromsizes=chromsizes)
    elif tileset.filetype == 'bigbed':
        chromsizes = get_chromsizes(tileset)
        return hgbb.tiles(tileset.datafile.path, tile_ids, chromsizes=chromsizes)
    elif tileset.filetype == 'multivec':
        return generate_1d_tiles(
                tileset.datafile.path,
                tile_ids,
                ctmu.get_single_tile,
                tileset_options)
    elif tileset.filetype == 'imtiles':
        return hgim.get_tiles(tileset.datafile.path, tile_ids, raw)
    elif tileset.filetype == 'bam':
        return ctb.tiles(
            tileset.datafile.path,
            tile_ids,
            index_filename=tileset.indexfile.path,
            max_tile_width=hss.MAX_BAM_TILE_WIDTH
        )
    else:
        filetype = tileset.filetype
        filepath = tileset.datafile.path

        if filetype in hgti.by_filetype:
            return hgti.by_filetype[filetype](filepath).tiles(tile_ids)

        return [(ti, {'error': 'Unknown tileset filetype: {}'.format(tileset.filetype)}) for ti in tile_ids]


