from __future__ import print_function

import cooler.contrib.higlass as cch
import logging
import numpy as np

logger = logging.getLogger(__name__)


def make_tiles(zoomLevel, x_pos, y_pos, dset, transform_type='default'):
    info = dset[1]
    divisor = 2 ** zoomLevel

    start1 = x_pos * info['max_width'] / divisor
    end1 = (x_pos + 1) * info['max_width'] / divisor
    start2 = y_pos * info['max_width'] / divisor
    end2 = (y_pos + 1) * info['max_width'] / divisor

    data = cch.get_data(
        dset[0], zoomLevel, start1, end1 - 1, start2, end2 - 1, transform_type
    )

    df = data[data['genome_start1'] >= start1]
    df = df[df['genome_start2'] >= start2]

    binsize = dset[0][str(zoomLevel)].attrs['bin-size']
    j = (df['genome_start1'].values - start1) // binsize
    i = (df['genome_start2'].values - start2) // binsize

    if 'balanced' in df:
        v = np.nan_to_num(df['balanced'].values)
    else:
        v = np.nan_to_num(df['count'].values)

    out = np.zeros(65536, dtype=np.float32)  # 256^2
    index = (i * 256) + j

    if len(index) > 0:
        # need this otherwise we get an error
        index = [int(i) for i in index]
        out[index] = v

    return out

def make_tiles(zoomLevel, x_pos, y_pos, dset, transform_type='default', x_width=1, y_width=1):
    '''
    Generate tiles for a given location. This function retrieves tiles for
    a rectangular region of width x_width and height y_width

    Arguments
    ---------
        zoomLevel: int
            The zoom level to retrieve tiles for (e.g. 0, 1, 2... )
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
    '''
    info = dset[1]
    divisor = 2 ** zoomLevel

    start1 = x_pos * info['max_width'] / divisor
    end1 = (x_pos + x_width) * info['max_width'] / divisor
    start2 = y_pos * info['max_width'] / divisor
    end2 = (y_pos + y_width) * info['max_width'] / divisor

    data = cch.get_data(
        dset[0], zoomLevel, start1, end1 - 1, start2, end2 - 1
    )

    #print("data:", data)

    #print("x_width:", x_width)
    #print("y_width:", y_width)
    # split out the individual tiles
    for x_offset in range(0, x_width):
        for y_offset in range(0, y_width):

            start1 = (x_pos + x_offset) * info['max_width'] / divisor
            end1 = (x_pos + x_offset+ 1) * info['max_width'] / divisor
            start2 = (y_pos + y_offset) * info['max_width'] / divisor
            end2 = (y_pos + y_offset + 1) * info['max_width'] / divisor

            df = data[data['genome_start1'] >= start1]
            df = df[df['genome_start1'] <= end1]

            df = df[df['genome_start2'] >= start2]
            df = df[df['genome_start2'] <= end2]

            binsize = dset[0].attrs[str(zoomLevel)]
            j = (df['genome_start1'].values - start1) // binsize
            i = (df['genome_start2'].values - start2) // binsize

            print("df:", df.size)

            if 'balanced' in df:
                v = np.nan_to_num(df['balanced'].values)
            else:
                v = np.nan_to_num(df['count'].values)

            out = np.zeros(65536, dtype=np.float32)  # 256^2
            index = [int(x) for x in (i * 256) + j]

            if len(v):
                out[index] = v

    return out
