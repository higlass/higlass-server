import base64
import tilesets.bigwig_tiles as bwt
import clodius.db_tiles as cdt
import clodius.hdf_tiles as hdft
import collections as col
import cooler.contrib.higlass as cch
import h5py
import itertools as it
import numpy as np
import os
import shutil
import time
import tempfile
import tilesets.utils as tut
from .tiles import make_tiles

import higlass_server.settings as hss

global mats
mats = {}

transform_descriptions = {}
transform_descriptions['weight'] = {'name': 'ICE', 'value': 'weight'}
transform_descriptions['KR'] = {'name': 'KR', 'value': 'KR'}
transform_descriptions['VC'] = {'name': 'VC', 'value': 'VC'}
transform_descriptions['VC_SQRT'] = {'name': 'VC_SQRT', 'value': 'VC_SQRT'}

def get_cached_datapath(relpath):
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
        return tut.get_datapath(relpath)

    orig_path = tut.get_datapath(relpath)
    cached_path = op.join(hss.CACHE_DIR, relpath)

    if op.exists(cached_path):
        # this file has already been cached
        print("here", cached_path)
        return cached_path

    with tempfile.TemporaryDirectory() as dirpath:
        tmp = op.join(dirpath, 'cached_file')
        shutil.copyfile(orig_path, tmp)

        # check to make sure the destination directory exists
        dest_dir = op.dirname(cached_path)
        print("dest_dir:", dest_dir)

        if not op.exists(dest_dir):
            os.makedirs(dest_dir)

        print("moving:", cached_path)
        print("stat:", os.stat(tmp))
        shutil.move(tmp, cached_path)
        print("stat:", os.stat(cached_path))
        print('abspath:', op.abspath(cached_path))

    return cached_path

def get_available_transforms(cooler):
    '''
    Get the available resolutions from a single cooler file.

    Parameters
    ----------
    cooler: h5py File
        A cooler file containing binned 2D data

    Returns
    -------
    transforms: dict
        A list of transforms available for this dataset
    '''
    transforms = set()

    f_for_zoom = cooler['bins']

    if 'weight' in f_for_zoom:
        transforms.add('weight')
    if 'KR' in f_for_zoom:
        transforms.add('KR')
    if 'VC' in f_for_zoom:
        transforms.add('VC')
    if 'VC_SQRT' in f_for_zoom:
        transforms.add('VC_SQRT')

    return transforms


def make_mats(dset):
    f = h5py.File(dset, 'r')

    if 'resolutions' in f:
        # this file contains raw resolutions so it'll return a different
        # sort of tileset info
        info = {"resolutions": tuple(sorted(map(int, list(f['resolutions'].keys())))) }
        mats[dset] = [f, info]

        # see which transforms are available, a transform has to be
        # available at every available resolution in order for it to
        # be provided as an option
        available_transforms_per_resolution = {}

        for resolution in info['resolutions']:
            available_transforms_per_resolution[resolution] = get_available_transforms(f['resolutions'][str(resolution)])

        all_available_transforms = set.intersection(*available_transforms_per_resolution.values())

        info['transforms'] = [transform_descriptions[t] for t in all_available_transforms]

        # get the genome size
        resolution = list(f['resolutions'].keys())[0]
        genome_length = int(sum(f['resolutions'][resolution]['chroms']['length']))
        
        info['max_pos'] = [genome_length, genome_length]
        info['min_pos'] = [1,1]
        return

    info = cch.get_info(dset)

    info["min_pos"] = [int(m) for m in info["min_pos"]]
    info["max_pos"] = [int(m) for m in info["max_pos"]]
    info["max_zoom"] = int(info["max_zoom"])
    info["max_width"] = int(info["max_width"])

    if "transforms" in info:
        info["transforms"] = list(info["transforms"])

    mats[dset] = [f, info]


def format_cooler_tile(tile_data_array):
    '''
    Format raw cooler cooler data into a more structured tile
    containing either float16 or float32 data along with a 
    dtype to differentiate between the two.

    Parameters
    ----------
    tile_data_array: np.array
        An array containing a flattened 256x256 chunk of data

    Returns
    -------
    tile_data: {'dense': str, 'dtype': str}
        The tile data reformatted to use float16 or float32 as the
        datatype. The dtype indicates which format is chosen.
    '''

    tile_data = {}

    min_dense = float(np.min(tile_data_array))
    max_dense = float(np.max(tile_data_array))

    tile_data["min_value"] = min_dense
    tile_data["max_value"] = max_dense

    min_f16 = np.finfo('float16').min
    max_f16 = np.finfo('float16').max

    if (
        max_dense > min_f16 and max_dense < max_f16 and
        min_dense > min_f16 and min_dense < max_f16
    ):
        tile_data['dense'] = base64.b64encode(tile_data_array.astype('float16')).decode('latin-1')
        tile_data['dtype'] = 'float16'
    else:
        tile_data['dense'] = base64.b64encode(tile_data_array.astype('float32')).decode('latin-1')
        tile_data['dtype'] = 'float32'

    return tile_data


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

def generate_multivec_tileset_info(filename):
    '''
    Return some information about this tileset that will
    help render it in on the client.

    Parameters
    ----------
    filename: str
      The filename of the h5py file containing the tileset info.

    Returns
    -------
    tileset_info: {}
      A dictionary containing the information describing
      this dataset
    '''
    f = h5py.File(filename, 'r')
    # a sorted list of resolutions, lowest to highest
    # awkward to write because a the numbers representing resolution
    # are datapoints / pixel so lower resolution is actually a higher
    # number
    resolutions = sorted([int(r) for r in f['resolutions'].keys()])[::-1]

    # the "leftmost" datapoint position
    # an array because higlass can display multi-dimensional
    # data
    min_pos = [0]

    # the "rightmost" datapoint position
    max_pos = [len(f['resolutions'][str(resolutions[-1])])]
    tile_size = 1024

    f.close()

    return {
      'resolutions': resolutions,
      'min_pos': min_pos,
      'tile_size': tile_size
    }

def get_single_multivec_tile(filename, tile_pos):
    '''
    Retrieve a single multivec tile from a multires file

    Parameters
    ----------
    filename: string
        The multires file containing the multivec data
    tile_pos: (z, x)
        The zoom level and position of this tile
    '''
    tileset_info = generate_multivec_tileset_info(filename)
    f = h5py.File(filename, 'r')
    
    # which resolution does this zoom level correspond to?
    resolution = tileset_info['resolutions'][tile_pos[0]]
    tile_size = tileset_info['tile_size']
    
    # where in the data does the tile start and end
    tile_start = tile_pos[1] * tile_size
    tile_end = tile_start + tile_size

    dense = f['resolutions'][str(resolution)][tile_start:tile_end]
    f.close()

    return dense

def generate_1d_tiles(filename, tile_ids, get_data_function):
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

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    generated_tiles = []

    for tile_id in tile_ids:
        tile_id_parts = tile_id.split('.')
        tile_position = list(map(int, tile_id_parts[1:3]))

        dense = get_data_function(filename, tile_position)

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


def generate_bigwig_tileset_info(tileset):
    '''
    Get the tileset info for a bigWig file

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from

    Returns
    -------
    tileset_info: {'min_pos': [], 
                    'max_pos': [], 
                    'tile_size': 1024, 
                    'max_zoom': 7
                    }
    '''
    chromsizes = bwt.get_chromsizes(tut.get_datapath(tileset.datafile.url))
    max_zoom = bwt.get_quadtree_depth(chromsizes)
    tile_size = 1024

    tileset_info = {
        'min_pos': [0],
        'max_pos': [tile_size * 2 ** max_zoom],
        'max_width': tile_size * 2 ** max_zoom,
        'tile_size': tile_size,
        'max_zoom': max_zoom
    }

    return tileset_info


def generate_bigwig_tiles(tileset, tile_ids):
    '''
    Generate tiles from a bigwig file.

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
        zoom_level = tile_position[0]

        # this doesn't combine multiple consequetive ids, which
        # would speed things up
        dense = bwt.get_bigwig_tile_by_id(
            tut.get_datapath(tileset.datafile.url), 
            zoom_level,
            tile_position[1])

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
                tut.get_datapath(tileset.datafile.url)
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



def generate_beddb_tiles(tileset, tile_ids):
    '''
    Generate tiles from a beddb file.

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    generated_tiles: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    tile_ids_by_zoom = bin_tiles_by_zoom(tile_ids).values()
    partitioned_tile_ids = list(it.chain(*[partition_by_adjacent_tiles(t, dimension=1) 
        for t in tile_ids_by_zoom]))

    generated_tiles = []

    for tile_group in partitioned_tile_ids:
        zoom_level = int(tile_group[0].split('.')[1])
        tileset_id = tile_group[0].split('.')[0]
        tile_positions = [[int(x) for x in t.split('.')[2:3]] for t in tile_group]

        if len(tile_positions) == 0:
            continue

        minx = min([t[0] for t in tile_positions])
        maxx = max([t[0] for t in tile_positions])

        t1 = time.time()
        tile_data_by_position = cdt.get_tiles(
            get_cached_datapath(tileset.datafile.url),
            zoom_level,
            minx,
            maxx - minx + 1
        )
        generated_tiles += [(".".join(map(str, [tileset_id] + [zoom_level] + [position])), tile_data)
            for (position, tile_data) in tile_data_by_position.items()]

    return generated_tiles

def generate_bed2ddb_tiles(tileset, tile_ids):
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

        cached_datapath = get_cached_datapath(tileset.datafile.url)
        tile_data_by_position = cdt.get_2d_tiles(
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
                tut.get_datapath(tileset.datafile.url)
            ),
            tile_position[0],
            tile_position[1]
        )

        tile_value = {'discrete': list([list([x.decode('utf-8') for x in d]) for d in dense])}

        generated_tiles += [(tile_id, tile_value)]

    return generated_tiles

def get_transform_type(tile_id):
    '''
    Get the transform type specified in the tile id.

    Parameters
    ----------
    cooler_tile_id: str
        A tile id for a 2D tile (cooler)

    Returns
    -------
    transform_type: str
        The transform type requested for this tile
    '''
    tile_id_parts = tile_id.split('.')

    if len(tile_id_parts) > 4:
        transform_method = tile_id_parts[4]
    else:
        transform_method = 'default'

    return transform_method

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

        transform_method = get_transform_type(tile_id)


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

def generate_cooler_tiles(tileset, tile_ids):
    '''
    Generate tiles from a cooler file.

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
    BINS_PER_TILE = 256
    filename = tut.get_datapath(tileset.datafile.url)

    if filename not in mats:
        # check if this tileset is open
        make_mats(filename)

    tileset_file_and_info = mats[filename]

    tile_ids_by_zoom_and_transform = bin_tiles_by_zoom_level_and_transform(tile_ids).values()
    partitioned_tile_ids = list(it.chain(*[partition_by_adjacent_tiles(t) 
        for t in tile_ids_by_zoom_and_transform]))

    generated_tiles = []

    for tile_group in partitioned_tile_ids:
        zoom_level = int(tile_group[0].split('.')[1])
        tileset_id = tile_group[0].split('.')[0]
        transform_type = get_transform_type(tile_group[0])
        tileset_info = tileset_file_and_info[1]
        tileset_file = tileset_file_and_info[0]

        if 'resolutions' in tileset_info:
            sorted_resolutions = sorted([int(r) for r in tileset_info['resolutions']], reverse=True)
            if zoom_level > len(sorted_resolutions):
                # this tile has too high of a zoom level specified
                continue

            resolution = sorted_resolutions[zoom_level]
            hdf_for_resolution = tileset_file['resolutions'][str(resolution)]
        else:
            if zoom_level > tileset_info['max_zoom']:
                # this tile has too high of a zoom level specified
                continue
            hdf_for_resolution = tileset_file[str(zoom_level)]
            resolution = (tileset_info['max_width'] / 2**zoom_level) / BINS_PER_TILE

        tile_positions = [[int(x) for x in t.split('.')[2:4]] for t in tile_group]

        # filter for tiles that are in bounds for this zoom level
        tile_width = resolution * BINS_PER_TILE
        tile_positions = list(filter(lambda x: x[0] * tile_width  < tileset_info['max_pos'][0]+1, tile_positions))
        tile_positions = list(filter(lambda x: x[1] * tile_width < tileset_info['max_pos'][1]+1, tile_positions))

        if len(tile_positions) == 0:
            # no in bounds tiles
            continue

        minx = min([t[0] for t in tile_positions])
        maxx = max([t[0] for t in tile_positions])

        miny = min([t[1] for t in tile_positions])
        maxy = max([t[1] for t in tile_positions])

        tile_data_by_position = make_tiles(hdf_for_resolution, 
                resolution,
                minx, miny, 
                transform_type,
                maxx-minx+1, maxy-miny+1)

        tiles = [(".".join(map(str, [tileset_id] + [zoom_level] + list(position) + [transform_type])), format_cooler_tile(tile_data))
                for (position, tile_data) in tile_data_by_position.items()]


        generated_tiles += tiles

    return generated_tiles

def generate_tiles(tileset_tile_ids):
    '''
    Generate a tiles for the give tile_ids.

    All of the tile_ids must come from the same tileset. This function
    will determine the appropriate handler this tile given the tileset's
    filetype and datatype

    Parameters
    ----------
    tileset: tilesets.models.Tileset object
        The tileset that the tile ids should be retrieved from
    tile_ids: [str,...]
        A list of tile_ids (e.g. xyx.0.0.1) identifying the tiles
        to be retrieved

    Returns
    -------
    tile_list: [(tile_id, tile_data),...]
        A list of tile_id, tile_data tuples
    '''
    tileset, tile_ids = tileset_tile_ids

    if tileset.filetype == 'hitile':
        return generate_hitile_tiles(tileset, tile_ids)
    elif tileset.filetype == 'beddb':
        return generate_beddb_tiles(tileset, tile_ids)
    elif tileset.filetype == 'bed2ddb':
        return generate_bed2ddb_tiles(tileset, tile_ids)
    elif tileset.filetype == 'hibed':
        return generate_hibed_tiles(tileset, tile_ids)
    elif tileset.filetype == 'cooler':
        return generate_cooler_tiles(tileset, tile_ids)
    elif tileset.filetype == 'bigwig':
        return generate_bigwig_tiles(tileset, tile_ids)
    elif tileset.filetype == 'multivec':
        return generate_1d_tiles(
                tut.get_datapath(tileset.datafile.url),
                tile_ids,
                get_single_multivec_tile)
    else:
        return [(ti, {'error': 'Unknown tileset filetype: {}'.format(tileset.filetype)}) for ti in tile_ids]


