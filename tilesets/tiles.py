from __future__ import print_function

import cooler
import cooler.contrib.higlass as cch
import logging
import numpy as np

logger = logging.getLogger(__name__)

def make_tiles(hdf_for_resolution, resolution, x_pos, y_pos, transform_type='default', x_width=1, y_width=1):
    '''
    Generate tiles for a given location. This function retrieves tiles for
    a rectangular region of width x_width and height y_width

    Parameters
    ---------
    hdf_for_resolution: h5py.File
        An HDF group containing the cooler for the given resolution
    x_pos: int
        The starting x position
    y_pos: int
        The starting y position
    cooler_file: string
        The filename of the cooler file to get the data from
    x_width: int 
        The number of tiles to retrieve along the x dimension
    y_width: int
        The number of tiles to retrieve along the y dimension

    Returns
    -------
    data_by_tilepos: {(x_pos, y_pos) : np.array}
        A dictionary of tile data indexed by tile positions
    '''
    BINS_PER_TILE = 256

    tile_size = resolution * BINS_PER_TILE

    start1 = x_pos * tile_size
    end1 = (x_pos + x_width) * tile_size
    start2 = y_pos * tile_size
    end2 = (y_pos + y_width) * tile_size

    '''
    print("transform_type:", transform_type);
    print('start1:', start1, end1)
    print('start2:', start2, end2)
    '''

    data = cch.get_data(
        hdf_for_resolution, start1, end1 - 1, start2, end2 - 1, 
        transform_type
    )

    #print("data:", data)

    #print("x_width:", x_width)
    #print("y_width:", y_width)
    # split out the individual tiles
    data_by_tilepos = {}

    for x_offset in range(0, x_width):
        for y_offset in range(0, y_width):

            start1 = (x_pos + x_offset) * tile_size
            end1 = (x_pos + x_offset+ 1) * tile_size
            start2 = (y_pos + y_offset) * tile_size
            end2 = (y_pos + y_offset + 1) * tile_size

            '''
            print("resolution:", resolution)
            print("tile_size", tile_size)
            print("x_pos:", x_pos, "x_offset", x_offset)
            print("start1", start1, 'end1', end1)
            print("start2", start2, 'end2', end2)
            '''

            df = data[data['genome_start1'] >= start1]
            df = df[df['genome_start1'] < end1]

            df = df[df['genome_start2'] >= start2]
            df = df[df['genome_start2'] < end2]

            binsize = resolution

            j = (df['genome_start1'].values - start1) // binsize
            i = (df['genome_start2'].values - start2) // binsize

            if 'balanced' in df:
                v = np.nan_to_num(df['balanced'].values)
            else:
                v = np.nan_to_num(df['count'].values)

            out = np.zeros(65536, dtype=np.float32)  # 256^2
            index = [int(x) for x in (i * 256) + j]

            if len(v):
                out[index] = v

            data_by_tilepos[(x_pos + x_offset, y_pos + y_offset)] = out

    return data_by_tilepos
